/**
 * @description Full video pipeline: crop 4:3->16:9, Dandere2x anime upscale, normalize audio, multi-bitrate HLS with free/premium playlists
 * @author fantasys
 * @revision 5
 * @output Pipeline completed successfully
 */
function Script() {
    let wf = Variables.file.FullName;
    let name = Variables.file.Orig.NameNoExtension;
    let outDir = '/media/hls-output/video/' + name;
    let ffmpeg = Variables.ffmpeg;
    let ffprobe = Variables.ffprobe;
    let tempDir = Variables.temp;
    let tempPathHost = Flow.TempPathHost;

    Logger.ILog('=== Full Pipeline + HLS ===');
    Logger.ILog('Input: ' + wf);
    Logger.ILog('Output dir: ' + outDir);
    Logger.ILog('TempDir: ' + tempDir);
    Logger.ILog('TempPathHost: ' + tempPathHost);

    // --- Step 1: Detect source dimensions ---
    let probeResult = Flow.Execute({
        command: ffprobe,
        argumentList: [
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=p=0',
            wf
        ]
    });

    let dims = (probeResult.standardOutput || '').trim().split(',');
    let srcW = parseInt(dims[0]) || 1440;
    let srcH = parseInt(dims[1]) || 1080;
    Logger.ILog('Source: ' + srcW + 'x' + srcH);

    // --- Step 2: Crop to 16:9 ---
    let aspectRatio = srcW / srcH;
    let cropFilter;
    if (aspectRatio < 16 / 9) {
        let targetH = Math.round(srcW * 9 / 16);
        let cropY = Math.round((srcH - targetH) / 2);
        if (cropY < 0) cropY = 0;
        cropFilter = 'crop=' + srcW + ':' + targetH + ':0:' + cropY;
        Logger.ILog('Crop height: ' + srcW + 'x' + targetH + ' (y=' + cropY + ')');
    } else if (aspectRatio > 16 / 9 + 0.01) {
        let targetW = Math.round(srcH * 16 / 9);
        let cropX = Math.round((srcW - targetW) / 2);
        if (cropX < 0) cropX = 0;
        cropFilter = 'crop=' + targetW + ':' + srcH + ':' + cropX + ':0';
        Logger.ILog('Crop width: ' + targetW + 'x' + srcH + ' (x=' + cropX + ')');
    } else {
        cropFilter = null;
        Logger.ILog('Already 16:9, no crop needed');
    }

    let croppedFile = tempDir + '/' + name + '_cropped.mp4';
    if (cropFilter) {
        Logger.ILog('Cropping...');
        let cropResult = Flow.Execute({
            command: ffmpeg,
            argumentList: [
                '-hide_banner', '-y', '-i', wf,
                '-vf', cropFilter,
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '16',
                '-c:a', 'copy',
                croppedFile
            ]
        });
        if (cropResult.exitCode !== 0) {
            Logger.ELog('Crop failed: ' + cropResult.exitCode);
            return -1;
        }
    } else {
        Flow.Execute({ command: 'cp', argumentList: [wf, croppedFile] });
    }

    // --- Step 3: Dandere2x anime upscale (docker-in-docker) ---
    let shortCropped = croppedFile.substring(croppedFile.lastIndexOf('/') + 1);
    let upscaledName = Flow.NewGuid() + '.mp4';
    let upscaledFile = tempDir + '/' + upscaledName;
    let useUpscaled = false;

    Logger.ILog('Attempting Dandere2x upscale...');
    Logger.ILog('  Input: ' + shortCropped);
    Logger.ILog('  Output: ' + upscaledName);

    let dandereResult = Flow.Execute({
        command: 'docker',
        argumentList: [
            'run',
            '--gpus', 'all',
            '--rm',
            '-v', tempPathHost + ':/host',
            'akaikatto/dandere2x',
            '-p', 'singleprocess',
            '-ws', './workspace/',
            '-i', '/host/' + shortCropped,
            '-o', '/host/' + upscaledName
        ]
    });

    if (dandereResult.standardOutput)
        Logger.ILog('Dandere2x stdout: ' + dandereResult.standardOutput);
    if (dandereResult.starndardError)
        Logger.ILog('Dandere2x stderr: ' + dandereResult.starndardError);

    if (dandereResult.exitCode === 0) {
        Logger.ILog('Dandere2x upscale succeeded!');
        useUpscaled = true;
    } else {
        Logger.WLog('Dandere2x failed (exit ' + dandereResult.exitCode + '), falling back to lanczos scaling');
    }

    // --- Step 4: Audio normalization (2-pass loudnorm) ---
    Logger.ILog('Pass 1: Measuring audio loudness...');
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

    // --- Step 5: Scale to 1080p + normalize audio -> processed MP4 ---
    let inputForProcess = useUpscaled ? upscaledFile : croppedFile;
    let processedFile = tempDir + '/' + name + '_processed.mp4';

    Logger.ILog('Pass 2: Scale + normalize (' + (useUpscaled ? 'from Dandere2x' : 'from cropped') + ')...');
    let processResult = Flow.Execute({
        command: ffmpeg,
        argumentList: [
            '-hide_banner', '-y', '-i', inputForProcess,
            '-vf', 'scale=1920:1080:flags=lanczos,setsar=1:1',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-af', loudnormFilter,
            '-c:a', 'aac', '-b:a', '192k', '-ac', '2',
            '-movflags', '+faststart',
            processedFile
        ]
    });

    if (processResult.exitCode !== 0) {
        Logger.ELog('Processing failed: ' + processResult.exitCode);
        if (processResult.standardError) Logger.ELog(processResult.standardError);
        return -1;
    }
    Logger.ILog('Processed file ready: ' + processedFile);

    // --- Step 6: Multi-bitrate HLS (360p/480p/720p/1080p) ---
    Flow.Execute({ command: 'mkdir', argumentList: ['-p', outDir + '/360p', outDir + '/480p', outDir + '/720p', outDir + '/1080p'] });
    Flow.Execute({ command: 'chmod', argumentList: ['-R', '777', outDir] });

    Logger.ILog('Creating multi-bitrate HLS (360p/480p/720p/1080p)...');
    let hlsResult = Flow.Execute({
        command: ffmpeg,
        argumentList: [
            '-hide_banner', '-y', '-i', processedFile,
            '-filter_complex',
            '[0:v]split=4[v1][v2][v3][v4];[v1]scale=-2:360[v360];[v2]scale=-2:480[v480];[v3]scale=-2:720[v720];[v4]copy[v1080]',
            // 360p
            '-map', '[v360]', '-map', '0:a',
            '-c:v:0', 'libx264', '-b:v:0', '600k',
            '-maxrate:v:0', '750k', '-bufsize:v:0', '1200k',
            '-preset', 'fast', '-g', '48',
            '-keyint_min', '48', '-sc_threshold', '0',
            '-c:a:0', 'aac', '-b:a:0', '96k', '-ac', '2',
            // 480p
            '-map', '[v480]', '-map', '0:a',
            '-c:v:1', 'libx264', '-b:v:1', '1000k',
            '-maxrate:v:1', '1200k', '-bufsize:v:1', '2000k',
            '-preset', 'fast', '-g', '48',
            '-keyint_min', '48', '-sc_threshold', '0',
            '-c:a:1', 'aac', '-b:a:1', '128k', '-ac', '2',
            // 720p
            '-map', '[v720]', '-map', '0:a',
            '-c:v:2', 'libx264', '-b:v:2', '2500k',
            '-maxrate:v:2', '3000k', '-bufsize:v:2', '5000k',
            '-preset', 'fast', '-g', '48',
            '-keyint_min', '48', '-sc_threshold', '0',
            '-c:a:2', 'aac', '-b:a:2', '192k', '-ac', '2',
            // 1080p
            '-map', '[v1080]', '-map', '0:a',
            '-c:v:3', 'libx264', '-b:v:3', '5000k',
            '-maxrate:v:3', '6000k', '-bufsize:v:3', '10000k',
            '-preset', 'fast', '-g', '48',
            '-keyint_min', '48', '-sc_threshold', '0',
            '-c:a:3', 'aac', '-b:a:3', '256k', '-ac', '2',
            // HLS output
            '-f', 'hls',
            '-hls_time', '6',
            '-hls_playlist_type', 'vod',
            '-hls_flags', 'independent_segments',
            '-hls_segment_type', 'mpegts',
            '-hls_segment_filename', outDir + '/%v/segment_%03d.ts',
            '-var_stream_map', 'v:0,a:0,name:360p v:1,a:1,name:480p v:2,a:2,name:720p v:3,a:3,name:1080p',
            outDir + '/%v/playlist.m3u8'
        ]
    });

    if (hlsResult.exitCode !== 0) {
        Logger.ELog('HLS failed: ' + hlsResult.exitCode);
        if (hlsResult.standardError) Logger.ELog(hlsResult.standardError);
        return -1;
    }

    // --- Step 7: Write master playlists (premium + free) ---
    let premiumPlaylist =
        '#EXTM3U\n' +
        '#EXT-X-VERSION:6\n' +
        '#EXT-X-STREAM-INF:BANDWIDTH=696000,RESOLUTION=640x360,CODECS="avc1.64001e,mp4a.40.2"\n' +
        '360p/playlist.m3u8\n' +
        '#EXT-X-STREAM-INF:BANDWIDTH=1128000,RESOLUTION=854x480,CODECS="avc1.64001e,mp4a.40.2"\n' +
        '480p/playlist.m3u8\n' +
        '#EXT-X-STREAM-INF:BANDWIDTH=2692000,RESOLUTION=1280x720,CODECS="avc1.64001f,mp4a.40.2"\n' +
        '720p/playlist.m3u8\n' +
        '#EXT-X-STREAM-INF:BANDWIDTH=5256000,RESOLUTION=1920x1080,CODECS="avc1.640028,mp4a.40.2"\n' +
        '1080p/playlist.m3u8\n';

    let freePlaylist =
        '#EXTM3U\n' +
        '#EXT-X-VERSION:6\n' +
        '#EXT-X-STREAM-INF:BANDWIDTH=696000,RESOLUTION=640x360,CODECS="avc1.64001e,mp4a.40.2"\n' +
        '360p/playlist.m3u8\n' +
        '#EXT-X-STREAM-INF:BANDWIDTH=1128000,RESOLUTION=854x480,CODECS="avc1.64001e,mp4a.40.2"\n' +
        '480p/playlist.m3u8\n' +
        '#EXT-X-STREAM-INF:BANDWIDTH=2692000,RESOLUTION=1280x720,CODECS="avc1.64001f,mp4a.40.2"\n' +
        '720p/playlist.m3u8\n';

    Flow.Execute({
        command: '/bin/sh',
        argumentList: ['-c', 'printf \'' + premiumPlaylist.replace(/'/g, "'\\''") + '\' > ' + outDir + '/master.m3u8']
    });

    Flow.Execute({
        command: '/bin/sh',
        argumentList: ['-c', 'printf \'' + freePlaylist.replace(/'/g, "'\\''") + '\' > ' + outDir + '/free.m3u8']
    });

    Logger.ILog('Master playlists written:');
    Logger.ILog('  premium: ' + outDir + '/master.m3u8 (360p/480p/720p/1080p)');
    Logger.ILog('  free:    ' + outDir + '/free.m3u8 (360p/480p/720p)');

    // Cleanup temp files
    Flow.Execute({ command: 'rm', argumentList: ['-f', croppedFile, processedFile] });
    if (useUpscaled) Flow.Execute({ command: 'rm', argumentList: ['-f', upscaledFile] });

    Logger.ILog('=== Pipeline complete! ===');
    Logger.ILog('HLS: ' + outDir);
    Logger.ILog('Upscaled: ' + (useUpscaled ? 'Dandere2x' : 'lanczos fallback'));
    return 1;
}
