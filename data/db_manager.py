import os
import time
import psycopg2
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector
import numpy as np
from collections import defaultdict

# DB_PATH was used for SQLite, can be removed or ignored.

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    # Use generic default for local testing if env not set, though docker-compose sets it.
    dsn = os.environ.get("DATABASE_URL", "postgresql://samesong:samesong_password@localhost:5432/samesong")
    conn = psycopg2.connect(dsn)
    return conn

def get_db_connection_with_retry(max_retries=5, initial_delay=1):
    """Establishes a connection to PostgreSQL with retry logic.
    
    Args:
        max_retries: Maximum number of connection attempts
        initial_delay: Initial delay in seconds (doubles with each retry)
    
    Returns:
        psycopg2 connection object
    
    Raises:
        Exception: If connection fails after all retries
    """
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return get_db_connection()
        except psycopg2.OperationalError as e:
            if attempt < max_retries - 1:
                print(f"Database connection attempt {attempt + 1}/{max_retries} failed. Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                print(f"Database connection failed after {max_retries} attempts.")
                raise e

def ensure_db_initialized():
    """Ensures that the database extensions and tables exist."""
    init_db()

def init_db():
    """Initializes the database with the required tables and extensions."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # 1. Enable pgvector extension
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        
        # Register vector type for this connection (technically needed for inserts/selects in this session)
        register_vector(conn)
        
        # 2. Songs Table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS songs (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                artist TEXT NOT NULL
            )
        ''')
        
        # 3. Fingerprints Table (FFT)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS fingerprints (
                hash TEXT NOT NULL,
                song_id INTEGER NOT NULL,
                "offset" INTEGER NOT NULL,
                FOREIGN KEY (song_id) REFERENCES songs (id) ON DELETE CASCADE
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_fingerprints_hash ON fingerprints (hash)')
        
        # 4. Vibe Fingerprints Table (CLAP)
        # Using 512 dimensions for CLAP
        cur.execute('''
            CREATE TABLE IF NOT EXISTS vibe_fingerprints (
                song_id INTEGER NOT NULL,
                embedding vector(512) NOT NULL,
                FOREIGN KEY (song_id) REFERENCES songs (id) ON DELETE CASCADE
            )
        ''')
        
        # Create HNSW index for fast cosine similarity search
        # vector_cosine_ops usually recommended for cosine distance
        cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_vibe_embedding 
            ON vibe_fingerprints 
            USING hnsw (embedding vector_cosine_ops)
        ''')

        conn.commit()
        
        # Note: Seed data loading is now handled by init_db_on_startup()
        # to avoid loading data multiple times during schema creation

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def add_song(title, artist, hashes):
    """
    Adds a song and its fingerprints to the database.
    hashes: List of (hash, offset) tuples/lists.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        cur.execute('INSERT INTO songs (title, artist) VALUES (%s, %s) RETURNING id', (title, artist))
        song_id = cur.fetchone()[0]
        
        # Batch insert fingerprints
        # hashes is expected to be a list of (hash_str, offset_int)
        # We need to structure data for execute_values: [(hash, song_id, offset), ...]
        fingerprint_data = [(h, song_id, o) for h, o in hashes]
        
        execute_values(
            cur,
            'INSERT INTO fingerprints (hash, song_id, "offset") VALUES %s',
            fingerprint_data
        )
        
        conn.commit()
        return song_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def add_vibe(song_id, embedding):
    """
    Adds a CLAP embedding to the database.
    embedding: numpy array (float32) of shape (512,)
    """
    conn = get_db_connection()
    try:
        register_vector(conn)
        cur = conn.cursor()
        
        # pgvector-python handles numpy arrays automatically
        cur.execute('INSERT INTO vibe_fingerprints (song_id, embedding) VALUES (%s, %s)', (song_id, embedding))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def check_song_exists(title, artist):
    """
    Checks if a song with the given title and artist already exists.
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT 1 FROM songs WHERE title = %s AND artist = %s', (title, artist))
        return cur.fetchone() is not None
    except Exception as e:
        print(f"Error checking song existence: {e}")
        return False
    finally:
        conn.close()

def find_matches(query_hashes):
    """
    Finds matching songs based on the query hashes.
    query_hashes: List of (hash, offset) tuples from the query audio.
    Returns: List of {"name": str, "timestamp": str, "confidence": float}
    """
    if not query_hashes:
        return []
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        query_map = defaultdict(list) # hash -> list of query_offsets
        for h, t in query_hashes:
            query_map[h].append(t)
            
        unique_hashes = list(query_map.keys())
        
        # In Postgres, we can use ANY(%s) for IN clauses with arrays, which is efficient
        # But we need to fetch (song_id, offset, hash)
        
        cur.execute('''
            SELECT song_id, "offset", hash 
            FROM fingerprints 
            WHERE hash = ANY(%s)
        ''', (unique_hashes,))
        
        matches = cur.fetchall()
        
        # The alignment logic remains the same as pure Python
        # --------------------------------------------------
        song_deltas = defaultdict(list)
        
        for song_id, db_offset, h in matches:
            for query_offset in query_map[h]:
                delta = db_offset - query_offset
                song_deltas[song_id].append(delta)
        
        results = []
        
        # Optimization: Fetch all song metadata in one go for matched IDs?
        # For now, let's process and fetch individual names (simpler port)
        # Or better: gather all song_ids and fetch map.
        
        matched_song_ids = list(song_deltas.keys())
        if not matched_song_ids:
            return []
            
        cur.execute('SELECT id, title, artist FROM songs WHERE id = ANY(%s)', (matched_song_ids,))
        song_info = {row[0]: {'title': row[1], 'artist': row[2]} for row in cur.fetchall()}
        
        for song_id, deltas in song_deltas.items():
            delta_counts = defaultdict(int)
            for d in deltas:
                delta_counts[d] += 1
            
            if not delta_counts:
                continue
                
            best_delta, score = max(delta_counts.items(), key=lambda x: x[1])
            
            if score > 5: # Threshold
                info = song_info.get(song_id)
                if info:
                    # offset to seconds
                    seconds = best_delta * 0.032
                    timestamp = f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"
                    confidence = min(score / 50.0, 1.0)
                    
                    results.append({
                        "name": f"{info['artist']} - {info['title']}",
                        "timestamp": timestamp,
                        "confidence": confidence,
                        "raw_score": score
                    })

        results.sort(key=lambda x: x["raw_score"], reverse=True)
        return results[:5]

    except Exception as e:
        print(f"Error in find_matches: {e}")
        return []
    finally:
        conn.close()

def find_vibe_matches(query_vector):
    """
    Finds vibe matches using cosine similarity (via pgvector).
    query_vector: numpy array (float32) of shape (512,) or (1, 512)
    """
    conn = get_db_connection()
    try:
        register_vector(conn)
        cur = conn.cursor()
        
        # Flatten and ensure type (pgvector/psycopg2 handles simple numpy arrays)
        query_vector = np.array(query_vector, dtype=np.float32).flatten()
        
        # Use Cosine Distance operator (<=>)
        # Distance = 1 - Cosine Similarity. 
        # So we want small distance for high similarity.
        # We also need to join with songs table to get metadata.
        
        cur.execute('''
            SELECT s.title, s.artist, v.embedding <=> %s as distance
            FROM vibe_fingerprints v
            JOIN songs s ON v.song_id = s.id
            ORDER BY distance ASC
            LIMIT 5
        ''', (query_vector,))
        
        rows = cur.fetchall()
        
        results = []
        for title, artist, distance in rows:
            # Convert distance back to similarity score for frontend compatibility
            # Similarity = 1 - Distance
            score = 1.0 - distance
            
            if score > 0.3: # Threshold
                results.append({
                    "name": f"{artist} - {title}",
                    "score": score
                })
        
        return results
        
    except Exception as e:
        print(f"Error in find_vibe_matches: {e}")
        return []
    finally:
        conn.close()

def init_db_on_startup():
    """Initialize database and load data from file on application startup.
    
    This function is designed to be called when the Flask app starts.
    It will:
    1. Wait for PostgreSQL to be ready (with retry logic)
    2. Create schema if it doesn't exist
    3. Load data from database.dat if the file exists
    
    This ensures data is always loaded into the database when Docker starts.
    """
    from pathlib import Path
    
    print("=" * 60)
    print("Starting database initialization...")
    print("=" * 60)
    
    try:
        # Step 1: Initialize schema with retry logic
        print("Step 1: Connecting to database and creating schema...")
        conn = get_db_connection_with_retry()
        conn.close()  # Close test connection
        
        # Now initialize the schema
        init_db()
        print("✓ Database schema initialized successfully")
        
        # Step 2: Load data from file if it exists
        print("\nStep 2: Checking for data file...")
        data_file = Path("data/database/database.dat")
        
        if data_file.exists():
            print(f"✓ Found data file: {data_file}")
            print("Loading data into database...")
            
            try:
                from ingestion.ingest import load_data_from_file_and_ingest
                load_data_from_file_and_ingest()
                print("✓ Data loading complete")
            except ImportError as e:
                print(f"⚠ Could not import ingestion module: {e}")
            except Exception as e:
                print(f"⚠ Error during data loading: {e}")
        else:
            print(f"⚠ No data file found at {data_file}")
            print("  Database will be empty. Run scraper to populate data.")
        
        print("\n" + "=" * 60)
        print("Database initialization complete!")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\n{'!' * 60}")
        print(f"ERROR: Database initialization failed: {e}")
        print(f"{'!' * 60}\n")
        # Don't raise - allow app to start even if DB init fails
        # This prevents the entire app from crashing
