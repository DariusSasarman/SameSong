const recordBtn = document.getElementById('recordBtn');
const btnIcon = document.getElementById('btnIcon');
const status = document.getElementById('status');
const vibeResults = document.getElementById('vibeResults');
const snippetResults = document.getElementById('snippetResults');
const resultsPanel = document.getElementById('resultsPanel');
const loader = document.getElementById('loader');
const canvas = document.getElementById('visualizer');
const canvasCtx = canvas.getContext('2d');

let audioCtx, analyser, dataArray, animationId, recorder;
let isRecording = false;
let recordTimeout;

async function startVisualizer(stream) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaStreamSource(stream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    dataArray = new Uint8Array(analyser.frequencyBinCount);
    draw();
}

function draw() {
    animationId = requestAnimationFrame(draw);
    analyser.getByteFrequencyData(dataArray);
    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
    let x = 0;
    const barWidth = (canvas.width / dataArray.length) * 2;
    for(let i = 0; i < dataArray.length; i++) {
        const barHeight = (dataArray[i] / 255) * canvas.height;
        canvasCtx.fillStyle = `rgba(0, 242, 255, ${dataArray[i]/255 + 0.15})`;
        canvasCtx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
        x += barWidth + 2;
    }
}

recordBtn.onclick = async () => {
    if (isRecording) {
        clearTimeout(recordTimeout);
        recorder.stop();
        return;
    }

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        resultsPanel.classList.add('hidden');
        status.innerText = "Listening... (Click to stop)";
        recordBtn.classList.add('recording');
        btnIcon.classList.remove('listen');
        btnIcon.classList.add('stop');

        startVisualizer(stream);

        recorder = new MediaRecorder(stream);
        const chunks = [];
        isRecording = true;

        recorder.ondataavailable = e => chunks.push(e.data);

        recorder.onstop = async () => {
            isRecording = false;
            recordBtn.classList.remove('recording');
            btnIcon.classList.remove('stop');
            btnIcon.classList.add('listen');
            cancelAnimationFrame(animationId);
            canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
            if (audioCtx) audioCtx.close();

            status.innerText = "Analyzing vibe...";
            loader.style.display = "block";

            const blob = new Blob(chunks, { type: 'audio/wav' });
            const formData = new FormData();
            formData.append('audio_file', blob, 'query.wav');

            try {
                const response = await fetch('/upload', { method: 'POST', body: formData });
                const { task_id } = await response.json();

                let data;
                while (true) {
                    const statusRes = await fetch(`/status/${task_id}`);

                    if (statusRes.status === 403) throw new Error("Unauthorized access.");
                    if (statusRes.status === 429) throw new Error("Too many requests.");

                    data = await statusRes.json();

                    if (data.status === "done") break;
                    if (data.status === "rejected") throw new Error("Request rejected by server.");
                    if (data.status === "failed") throw new Error("Analysis failed.");
                    if (data.status === "error") throw new Error(data.message);
                    // Wait 2 seconds before checking again
                    await new Promise(r => setTimeout(r, 2000));
                }

                loader.style.display = "none";
                resultsPanel.classList.remove('hidden');

                vibeResults.innerHTML = data.vibe_matches.map(m => `
                    <li><span class="score">${Math.round(m.score * 100)}%</span> <span class="name">${m.name}</span></li>
                `).join('');

                snippetResults.innerHTML = data.snippet_matches.map(m => `
                    <li><span class="name">${m.name}</span> <span class="time">At ${m.timestamp}</span></li>
                `).join('');

                status.innerText = "Analysis Complete";
            } catch (err) {
                loader.style.display = "none";
                status.innerText = err.message || "Error occurred." + " Please try again later.";
            }
        };

        recorder.start();
        recordTimeout = setTimeout(() => { if (isRecording) recorder.stop(); }, 30000);
    } catch (err) {
        console.error(err);
        status.innerText = "Mic Error";
    }
};