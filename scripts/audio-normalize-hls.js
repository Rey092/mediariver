/**
 * @description Normalize audio (2-pass loudnorm) and package as multi-bitrate HLS (128k/256k)
 * @author fantasys
 * @revision 1
 * @output Audio HLS output created successfully
 */
function Script() {
    let wf = Variables.file.FullName;
    let name = Variables.file.Orig.NameNoExtension;
    let outDir = '/media/hls-output/audio/' + name;
    let ffmpeg = Variables.ffmpeg;
    let tempDir = Variables.temp;
    let tempFile = tempDir + '/' + name + '_normalized.m4a';

    Logger.ILog('=== Audio Normalize + HLS ===');
    Logger.ILog('Input: ' + wf);
    Logger.ILog('Output dir: ' + outDir);

    // --- Step 1: Measure loudness (pass 1) ---
    Logger.ILog('Pass 1: Measuring loudness...');
    let measureResult = Flow.Execute({
        command: ffmpeg,
        argumentList: [
            '-hide_banner', '-y', '-i', wf,
            '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json',
            '-f', 'null', '/dev/null'
        ]
    });

    let stderr = measureResult.standardError || measureResult.output || '';
    let loudnormFilter = 'loudnorm=I=-16:TP=-1.5:LRA=11';

    let miMatch = stderr.match(/"input_i"\s*:\s*"([^"]+)"/);
    let mtpMatch = stderr.match(/"input_tp"\s*:\s*"([^"]+)"/);
    let mlraMatch = stderr.match(/"input_lra"\s*:\s*"([^"]+)"/);
    let mthreshMatch = stderr.match(/"input_thresh"\s*:\s*"([^"]+)"/);
    let moffsetMatch = stderr.match(/"target_offset"\s*:\s*"([^"]+)"/);

    if (miMatch && mtpMatch) {
        loudnormFilter = 'loudnorm=I=-16:TP=-1.5:LRA=11' +
            ':measured_I=' + miMatch[1] +
            ':measured_TP=' + mtpMatch[1] +
            ':measured_LRA=' + (mlraMatch ? mlraMatch[1] : '11') +
            ':measured_thresh=' + (mthreshMatch ? mthreshMatch[1] : '-26') +
            ':offset=' + (moffsetMatch ? moffsetMatch[1] : '0') +
            ':linear=true';
        Logger.ILog('2-pass loudnorm: I=' + miMatch[1] + ' TP=' + mtpMatch[1]);
    } else {
        Logger.ILog('Using single-pass loudnorm');
    }

    // --- Step 2: Normalize audio -> temp AAC file ---
    Logger.ILog('Pass 2: Normalizing audio...');
    let normResult = Flow.Execute({
        command: ffmpeg,
        argumentList: [
            '-hide_banner', '-y', '-i', wf,
            '-af', loudnormFilter,
            '-c:a', 'aac', '-b:a', '256k', '-ac', '2',
            '-movflags', '+faststart',
            tempFile
        ]
    });

    if (normResult.exitCode !== 0) {
        Logger.ELog('Normalization failed: ' + normResult.exitCode);
        if (normResult.standardError) Logger.ELog(normResult.standardError);
        return -1;
    }
    Logger.ILog('Normalized file ready');

    // --- Step 3: HLS multi-bitrate (128k + 256k) ---
    Flow.Execute({ command: 'mkdir', argumentList: ['-p', outDir + '/128k', outDir + '/256k'] });
    Flow.Execute({ command: 'chmod', argumentList: ['-R', '777', outDir] });

    Logger.ILog('Creating 128k HLS variant...');
    let hls128 = Flow.Execute({
        command: ffmpeg,
        argumentList: [
            '-hide_banner', '-y', '-i', tempFile,
            '-map', '0:a', '-c:a', 'aac', '-b:a', '128k', '-ac', '2',
            '-f', 'hls',
            '-hls_time', '10',
            '-hls_playlist_type', 'vod',
            '-hls_segment_type', 'mpegts',
            '-hls_segment_filename', outDir + '/128k/segment_%03d.ts',
            outDir + '/128k/playlist.m3u8'
        ]
    });

    if (hls128.exitCode !== 0) {
        Logger.ELog('HLS 128k failed: ' + hls128.exitCode);
        return -1;
    }

    Logger.ILog('Creating 256k HLS variant...');
    let hls256 = Flow.Execute({
        command: ffmpeg,
        argumentList: [
            '-hide_banner', '-y', '-i', tempFile,
            '-map', '0:a', '-c:a', 'aac', '-b:a', '256k', '-ac', '2',
            '-f', 'hls',
            '-hls_time', '10',
            '-hls_playlist_type', 'vod',
            '-hls_segment_type', 'mpegts',
            '-hls_segment_filename', outDir + '/256k/segment_%03d.ts',
            outDir + '/256k/playlist.m3u8'
        ]
    });

    if (hls256.exitCode !== 0) {
        Logger.ELog('HLS 256k failed: ' + hls256.exitCode);
        return -1;
    }

    // --- Step 4: Write master playlist ---
    let masterContent =
        '#EXTM3U\n' +
        '#EXT-X-VERSION:3\n' +
        '#EXT-X-STREAM-INF:BANDWIDTH=128000,CODECS="mp4a.40.2"\n' +
        '128k/playlist.m3u8\n' +
        '#EXT-X-STREAM-INF:BANDWIDTH=256000,CODECS="mp4a.40.2"\n' +
        '256k/playlist.m3u8\n';

    let writeResult = Flow.Execute({
        command: '/bin/sh',
        argumentList: ['-c', 'printf \'' + masterContent.replace(/'/g, "'\\''") + '\' > ' + outDir + '/master.m3u8']
    });

    if (writeResult.exitCode !== 0) {
        Logger.ELog('Failed to write master playlist');
        return -1;
    }

    // Cleanup
    Flow.Execute({ command: 'rm', argumentList: ['-f', tempFile] });

    Logger.ILog('=== Audio pipeline complete! ===');
    Logger.ILog('HLS: ' + outDir);
    return 1;
}
