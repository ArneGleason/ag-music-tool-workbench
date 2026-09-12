loadAPI(21);
host.defineController("AG Music Tool Workbench", "Live Project Bridge", "0.1", "3b75dcd8-1b90-4e7e-8f8b-fc1ce481c5df", "AMTW");
host.defineMidiPorts(0, 0);

// Outgoing localhost TCP avoids the persistent listening-port problem of the
// older OSC extension. No arbitrary code or file operation is accepted here.
var connection = null, tracks = [], transport, application, revision = 0;
var session = String(Date.now()) + "-" + Math.random(), busy = false;
var completed = {}, completedOrder = [];
function watch(value) { value.markInterested(); value.addValueObserver(function () { revision++; }); return value; }
function init() {
    application = host.createApplication(); watch(application.projectName());
    transport = host.createTransport();
    transport.tempo().markInterested(); transport.isPlaying().markInterested(); transport.playPosition().markInterested();
    var bank = host.createTrackBank(64, 0, 0, true);
    for (var i = 0; i < 64; i++) {
        var t = bank.getItemAt(i);
        [t.exists(), t.name(), t.position(), t.trackType(), t.isGroup(), t.mute(), t.solo(), t.volume(), t.pan()].forEach(watch);
        tracks.push(t);
    }
    connect();
}
function connect() {
    if (!connection) {
        try {
            host.connectToRemoteHost("127.0.0.1", 8766, function (c) {
                connection = c;
                c.setDisconnectCallback(function () { if (connection === c) connection = null; });
                c.setReceiveCallback(function (bytes) {
                    try { handle(JSON.parse(String(new java.lang.String(bytes, "UTF-8")))); }
                    catch (e) { send({id: null, error: String(e)}); }
                });
                send({hello: "amtw-live", session: session});
            });
        } catch (e) { /* Broker may start after Bitwig. Retry without popups. */ }
    }
    host.scheduleTask(connect, 2000);
}
function send(value) {
    if (!connection) return;
    // RemoteConnection.send sends raw bytes; its receive callback removes the
    // four-byte big-endian frame header. Mirror that framing in both directions.
    var body = new java.lang.String(JSON.stringify(value)).getBytes("UTF-8");
    var out = [(body.length >>> 24) & 255, (body.length >>> 16) & 255, (body.length >>> 8) & 255, body.length & 255];
    for (var i = 0; i < body.length; i++) out.push(body[i]);
    for (var j = 0; j < 4; j++) if (out[j] > 127) out[j] -= 256;
    try { connection.send(out); } catch (e) { connection = null; }
}
function trackState(t, index) {
    return {index: index, position: t.position().get(), name: t.name().get(), type: t.trackType().get(),
        group: t.isGroup().get(), mute: t.mute().get(), solo: t.solo().get(),
        volume: t.volume().get(), pan: t.pan().get()};
}
function snapshot() {
    var out = [];
    for (var i = 0; i < tracks.length; i++) if (tracks[i].exists().get()) out.push(trackState(tracks[i], i));
    return {session: session, revision: revision, project: application.projectName().get(),
        tracks: out, capacity: 64, possiblyTruncated: tracks[63].exists().get(),
        transport: {playing: transport.isPlaying().get(), tempoBpm: transport.tempo().getRaw(), beat: transport.playPosition().get()},
        capabilities: ["snapshot", "set_track:name,mute,solo,volume,pan"],
        limitations: "No clip, note, tempo-envelope, audio export/import or device edits in this version. Volume/pan are normalized 0..1."};
}
function finish(req, result) {
    busy = false;
    var response = {id: req.id, result: result};
    completed[req.id] = {request: JSON.stringify(req), response: response}; completedOrder.push(req.id);
    if (completedOrder.length > 100) delete completed[completedOrder.shift()];
    send(response);
}
function handle(req) {
    var ownsWrite = false;
    if (typeof req.id !== "string" || req.id.length > 100) throw Error("Request id required");
    if (completed[req.id]) {
        if (completed[req.id].request !== JSON.stringify(req)) throw Error("Request id reused with different payload");
        send(completed[req.id].response); return;
    }
    try {
        if (req.op === "snapshot") { send({id: req.id, result: snapshot()}); return; }
        if (req.op !== "set_track") throw Error("Unsupported operation");
        if (busy) throw Error("Another edit is awaiting readback");
        if (req.session !== session || req.revision !== revision) throw Error("Stale snapshot; read again before editing");
        if (typeof req.index !== "number" || req.index % 1 || req.index < 0 || req.index >= tracks.length) throw Error("Invalid track index");
        var t = tracks[req.index];
        if (!t.exists().get() || t.name().get() !== req.expectedName) throw Error("Track identity changed");
        var field = req.field, value = req.value;
        if (["name", "mute", "solo", "volume", "pan"].indexOf(field) < 0) throw Error("Unsupported field");
        if (field === "name" && (typeof value !== "string" || !value.length || value.length > 200)) throw Error("Name must contain 1..200 characters");
        if ((field === "mute" || field === "solo") && typeof value !== "boolean") throw Error("Boolean required");
        if ((field === "volume" || field === "pan") && (typeof value !== "number" || !isFinite(value) || value < 0 || value > 1)) throw Error("Normalized value 0..1 required");
        var before = trackState(t, req.index);
        busy = true; ownsWrite = true; revision++; // Invalidate competing requests before observers arrive.
        t[field]().set(value);
        host.scheduleTask(function () {
            var after = trackState(t, req.index);
            var matched = typeof value === "number" ? Math.abs(after[field] - value) < 0.00001 : after[field] === value;
            finish(req, {verified: matched, before: before, after: after, snapshot: snapshot()});
        }, 200);
    } catch (e) { if (ownsWrite) busy = false; send({id: req.id, error: String(e)}); }
}
function flush() {}
function exit() { connection = null; }
