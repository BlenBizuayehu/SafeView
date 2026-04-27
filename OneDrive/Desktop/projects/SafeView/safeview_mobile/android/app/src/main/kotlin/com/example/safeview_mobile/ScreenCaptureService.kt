package com.example.safeview_mobile

import android.app.*
import android.content.Context
import android.content.Intent
import android.graphics.*
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.*
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.IBinder
import android.util.DisplayMetrics
import android.view.*
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class ScreenCaptureService : Service() {
    companion object {
        private const val CHANNEL_ID = "safeview_capture_channel"
        private const val NOTIFICATION_ID = 100
        private const val EXTRA_RESULT_CODE = "resultCode"
        private const val EXTRA_DATA_INTENT = "dataIntent"
        private const val EXTRA_SENSITIVITY = "sensitivity"
        private const val EXTRA_FILTER_NUDITY = "filter_nudity"
        private const val EXTRA_FILTER_VIOLENCE = "filter_violence"
        private const val EXTRA_FILTER_PROFANITY = "filter_profanity"
        private const val TARGET_URL = "http://10.0.2.2:8000/analyze-image"
    }

    private val client = OkHttpClient()
    private var projection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var imageReader: ImageReader? = null

    private var lastSentMs: Long = 0
    private val throttleMs = 600L // ~1-2 FPS

    // Overlay
    private lateinit var windowManager: WindowManager
    private var overlayView: View? = null
    private lateinit var layoutParams: WindowManager.LayoutParams

    // Audio
    private var audioManager: AudioManager? = null
    private var audioJob: Job? = null
    private var sensitivity: Float = 0.75f
    private var filterNudity: Boolean = true
    private var filterViolence: Boolean = true
    private var filterProfanity: Boolean = true
    private var blockedThemes: ArrayList<String> = arrayListOf()

    // Metadata blocking
    private var metaJob: Job? = null
    private var lastTitle: String = ""
    private var lastMetaCheckMs: Long = 0
    private var metadataBlocked: Boolean = false
    private var blockReason: String = ""
    private var fullMaskView: FrameLayout? = null

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
        windowManager = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        setupOverlay()
        audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        try {
            val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, Activity.RESULT_CANCELED) ?: Activity.RESULT_CANCELED
            val dataIntent = intent?.getParcelableExtra<Intent>(EXTRA_DATA_INTENT)
            sensitivity = intent?.getFloatExtra(EXTRA_SENSITIVITY, 0.75f) ?: 0.75f
            filterNudity = intent?.getBooleanExtra(EXTRA_FILTER_NUDITY, true) ?: true
            filterViolence = intent?.getBooleanExtra(EXTRA_FILTER_VIOLENCE, true) ?: true
            filterProfanity = intent?.getBooleanExtra(EXTRA_FILTER_PROFANITY, true) ?: true
            blockedThemes = intent?.getStringArrayListExtra("blocked_themes") ?: arrayListOf()
            val mpm = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
            projection = mpm.getMediaProjection(resultCode, dataIntent!!)

            initializeCapture()
        } catch (e: Exception) {
            stopSelf()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        imageReader?.setOnImageAvailableListener(null, null)
        imageReader?.close()
        virtualDisplay?.release()
        projection?.stop()
        overlayView?.let { windowManager.removeViewImmediate(it) }
        fullMaskView?.let { windowManager.removeViewImmediate(it) }
        audioJob?.cancel()
        metaJob?.cancel()
        serviceScope.cancel()
    }

    private fun initializeCapture() {
        val metrics = DisplayMetrics()
        val display = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            display
        } else {
            @Suppress("DEPRECATION")
            windowManager.defaultDisplay
        }
        display?.getRealMetrics(metrics)
        val width = metrics.widthPixels
        val height = metrics.heightPixels
        val density = metrics.densityDpi

        imageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
        virtualDisplay = projection?.createVirtualDisplay(
            "SafeViewCapture",
            width,
            height,
            density,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_PUBLIC,
            imageReader?.surface,
            null,
            null
        )

        imageReader?.setOnImageAvailableListener({ reader ->
            val now = System.currentTimeMillis()
            if (now - lastSentMs < throttleMs) {
                // Drain image without processing to avoid memory leak
                reader.acquireLatestImage()?.close()
                return@setOnImageAvailableListener
            }
            val image = reader.acquireLatestImage() ?: return@setOnImageAvailableListener
            lastSentMs = now
            try {
                val bitmap = imageToBitmap(image)
                if (bitmap != null) {
                    val jpeg = bitmapToJpeg(bitmap, 70)
                    // BR-02: Purging frame from RAM immediately after analysis
                    bitmap.recycle()
                    if (jpeg != null) {
                        serviceScope.launch {
                            sendFrame(jpeg, width, height)
                        }
                    }
                }
            } catch (e: Exception) {
            } finally {
                // BR-02: Purging frame from RAM immediately after analysis
                image.close()
            }
        }, null)

        // Start audio capture loop (API 29+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            audioJob = serviceScope.launch(Dispatchers.IO) {
                runAudioLoop()
            }
        }

        // Start metadata polling loop
        metaJob = serviceScope.launch(Dispatchers.IO) {
            runMetadataLoop()
        }
    }

    private fun imageToBitmap(image: android.media.Image): Bitmap? {
        val plane = image.planes[0]
        val buffer = plane.buffer
        val pixelStride = plane.pixelStride
        val rowStride = plane.rowStride
        val rowPadding = rowStride - pixelStride * image.width
        val bmp = Bitmap.createBitmap(
            image.width + rowPadding / pixelStride,
            image.height,
            Bitmap.Config.ARGB_8888
        )
        bmp.copyPixelsFromBuffer(buffer)
        return Bitmap.createBitmap(bmp, 0, 0, image.width, image.height)
    }

    private fun bitmapToJpeg(bitmap: Bitmap, quality: Int): ByteArray? {
        return try {
            val stream = java.io.ByteArrayOutputStream()
            bitmap.compress(Bitmap.CompressFormat.JPEG, quality, stream)
            stream.toByteArray()
        } catch (_: Exception) {
            null
        }
    }

    private suspend fun sendFrame(jpegBytes: ByteArray, screenW: Int, screenH: Int) {
        try {
            val requestBody = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart(
                    "image",
                    "frame.jpg",
                    RequestBody.create("image/jpeg".toMediaType(), jpegBytes)
                )
                .addFormDataPart("sensitivity", sensitivity.toString())
                .addFormDataPart("filter_nudity", filterNudity.toString())
                .addFormDataPart("filter_violence", filterViolence.toString())
                .build()

            val req = Request.Builder()
                .url(TARGET_URL)
                .post(requestBody)
                .build()

            val resp = client.newCall(req).execute()
            val bodyStr = resp.body?.string() ?: ""
            resp.close()
            if (resp.isSuccessful && bodyStr.isNotEmpty()) {
                parseAndDisplayOverlay(bodyStr, screenW, screenH)
            } else {
                hideOverlay()
            }
        } catch (_: Exception) {
            hideOverlay()
        }
    }

    private fun parseAndDisplayOverlay(json: String, screenW: Int, screenH: Int) {
        try {
            val obj = JSONObject(json)
            val status = obj.optString("status", "")
            if (status != "success") {
                hideOverlay()
                return
            }
            val analysis = obj.optJSONArray("analysis") ?: run {
                hideOverlay(); return
            }
            if (analysis.length() == 0) {
                hideOverlay(); return
            }

            // For simplicity, use first detection
            val first = analysis.getJSONObject(0)
            val label = first.optString("label", "Unknown")
            val score = first.optDouble("score", 0.0)
            val box = first.optJSONObject("box") ?: run {
                hideOverlay(); return
            }
            val x = box.optDouble("x", 0.0)
            val y = box.optDouble("y", 0.0)
            val w = box.optDouble("width", 0.0)
            val h = box.optDouble("height", 0.0)

            val pxX = (x * screenW).toInt()
            val pxY = (y * screenH).toInt()
            val pxW = (w * screenW).toInt().coerceAtLeast(1)
            val pxH = (h * screenH).toInt().coerceAtLeast(1)

            sendStatus("Vision: $label detected (${(score * 100).toInt()}%) - BLUR APPLIED")
            showOverlay(pxX, pxY, pxW, pxH)
        } catch (_: Exception) {
            hideOverlay()
        }
    }

    private fun setupOverlay() {
        overlayView = FrameLayout(this).apply {
            setBackgroundColor(Color.parseColor("#80000000")) // translucent black
            visibility = View.GONE
        }
        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        else
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE

        layoutParams = WindowManager.LayoutParams(
            0,
            0,
            type,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        )
        layoutParams.gravity = Gravity.TOP or Gravity.START
        windowManager.addView(overlayView, layoutParams)

        // Full-screen mask for metadata blocking
        fullMaskView = FrameLayout(this).apply {
            setBackgroundColor(Color.parseColor("#E6000000")) // more opaque black
            visibility = View.GONE
            val tv = android.widget.TextView(this@ScreenCaptureService).apply {
                setTextColor(Color.WHITE)
                textSize = 18f
                text = "Content Blocked by SafeView"
                setPadding(24, 24, 24, 24)
                gravity = Gravity.CENTER
            }
            addView(tv, FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            ).apply { gravity = Gravity.CENTER })
        }
        val fullParams = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            else
                @Suppress("DEPRECATION")
                WindowManager.LayoutParams.TYPE_PHONE,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        )
        fullParams.gravity = Gravity.TOP or Gravity.START
        windowManager.addView(fullMaskView, fullParams)
    }

    private fun showOverlay(x: Int, y: Int, w: Int, h: Int) {
        serviceScope.launch(Dispatchers.Main) {
            if (metadataBlocked) {
                // Priority: metadata block wins, don't show bbox overlay
                overlayView?.visibility = View.GONE
                fullMaskView?.visibility = View.VISIBLE
                return@launch
            }
            overlayView?.visibility = View.VISIBLE
            layoutParams.x = x
            layoutParams.y = y
            layoutParams.width = w
            layoutParams.height = h
            overlayView?.let { windowManager.updateViewLayout(it, layoutParams) }
        }
    }

    private fun hideOverlay() {
        serviceScope.launch(Dispatchers.Main) {
            if (metadataBlocked) {
                fullMaskView?.visibility = View.VISIBLE
            } else {
                fullMaskView?.visibility = View.GONE
                overlayView?.visibility = View.GONE
            }
        }
    }

    // ================== Metadata Loop ==================
    private suspend fun runMetadataLoop() {
        while (isActive) {
            try {
                val now = System.currentTimeMillis()
                if (now - lastMetaCheckMs >= 7000L) { // every ~7s
                    lastMetaCheckMs = now
                    val title = getCurrentContextTitle()
                    if (title.isNotBlank() && title != lastTitle) {
                        lastTitle = title
                        queryMetadataAndUpdateMask(title)
                    }
                }
            } catch (_: Exception) {
            }
            delay(1000L)
        }
    }

    // Placeholder: try to use app label as a proxy for title.
    private fun getCurrentContextTitle(): String {
        return try {
            val am = getSystemService(Context.ACTIVITY_SERVICE) as android.app.ActivityManager
            @Suppress("DEPRECATION")
            val task = am.runningAppProcesses?.firstOrNull()
            val pkg = task?.processName ?: return ""
            val pm = packageManager
            val appInfo = pm.getApplicationInfo(pkg, 0)
            pm.getApplicationLabel(appInfo).toString()
        } catch (_: Exception) {
            ""
        }
    }

    private fun queryMetadataAndUpdateMask(title: String) {
        try {
            val json = JSONObject()
            json.put("title", title)
            val themes = blockedThemes
            val arr = org.json.JSONArray()
            themes.forEach { arr.put(it) }
            json.put("blocked_themes", arr)

            val body = okhttp3.RequestBody.create("application/json".toMediaType(), json.toString())
            val req = Request.Builder()
                .url("http://10.0.2.2:8000/analyze-metadata")
                .post(body)
                .build()
            client.newCall(req).execute().use { resp ->
                val bodyStr = resp.body?.string() ?: ""
                if (!resp.isSuccessful || bodyStr.isEmpty()) {
                    clearMetadataBlock()
                    return
                }
                val obj = JSONObject(bodyStr)
                val status = obj.optString("status", "ALLOW")
                val reason = obj.optString("reason", "")
                if (status == "BLOCK") {
                    applyMetadataBlock(reason)
                } else {
                    clearMetadataBlock()
                }
            }
        } catch (_: Exception) {
            clearMetadataBlock()
        }
    }

    private fun applyMetadataBlock(reason: String) {
        metadataBlocked = true
        blockReason = reason
        sendStatus("Metadata: BLOCK - $reason")
        serviceScope.launch(Dispatchers.Main) {
            // Update message text
            (fullMaskView?.getChildAt(0) as? android.widget.TextView)?.text =
                "Content Blocked by SafeView\n(Restricted Theme: $reason)"
            fullMaskView?.visibility = View.VISIBLE
            overlayView?.visibility = View.GONE
        }
    }

    private fun clearMetadataBlock() {
        metadataBlocked = false
        blockReason = ""
        sendStatus("Metadata: ALLOW")
        serviceScope.launch(Dispatchers.Main) {
            fullMaskView?.visibility = View.GONE
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "SafeView Capture",
                NotificationManager.IMPORTANCE_LOW
            )
            channel.description = "Screen capture in progress"
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(): Notification {
        val notifBuilder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("SafeView Protection")
            .setContentText("Analyzing screen for sensitive content")
            .setSmallIcon(android.R.drawable.ic_menu_view)
            .setOngoing(true)
        return notifBuilder.build()
    }

    // ================== Audio Capture & Mute Logic ==================
    private suspend fun runAudioLoop() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return
        val proj = projection ?: return
        val config = AudioPlaybackCaptureConfiguration.Builder(proj)
            .addMatchingUsage(AudioAttributes.USAGE_MEDIA)
            .build()

        val sampleRate = 16000
        val channelConfig = AudioFormat.CHANNEL_IN_MONO
        val encoding = AudioFormat.ENCODING_PCM_16BIT
        val minBuf = AudioRecord.getMinBufferSize(sampleRate, channelConfig, encoding)
        if (minBuf <= 0) return

        val record = AudioRecord.Builder()
            .setAudioPlaybackCaptureConfig(config)
            .setAudioFormat(
                AudioFormat.Builder()
                    .setEncoding(encoding)
                    .setSampleRate(sampleRate)
                    .setChannelMask(channelConfig)
                    .build()
            )
            .setBufferSizeInBytes(minBuf * 4)
            .build()

        try {
            record.startRecording()
            val chunkSeconds = 2  // 2-second chunks
            val chunkSize = sampleRate * 2 * chunkSeconds // 16-bit mono -> 2 bytes per sample
            val buffer = ByteArray(chunkSize)

            while (isActive) {
                var readTotal = 0
                while (readTotal < chunkSize && isActive) {
                    val r = record.read(buffer, readTotal, chunkSize - readTotal)
                    if (r <= 0) break
                    readTotal += r
                }
                if (readTotal > 0) {
                    val wav = pcmToWav(buffer, readTotal, sampleRate, 1, 16)
                    sendAudioForAnalysis(wav)
                }
            }
        } catch (_: Exception) {
        } finally {
            try {
                record.stop()
            } catch (_: Exception) {}
            record.release()
        }
    }

    private fun pcmToWav(pcmData: ByteArray, dataLen: Int, sampleRate: Int, channels: Int, bitsPerSample: Int): ByteArray {
        val byteRate = sampleRate * channels * bitsPerSample / 8
        val totalDataLen = dataLen + 36
        val header = java.nio.ByteBuffer.allocate(44).order(java.nio.ByteOrder.LITTLE_ENDIAN)
        // RIFF header
        header.put("RIFF".toByteArray())
        header.putInt(totalDataLen)
        header.put("WAVE".toByteArray())
        // fmt subchunk
        header.put("fmt ".toByteArray())
        header.putInt(16) // Subchunk1Size for PCM
        header.putShort(1) // PCM format
        header.putShort(channels.toShort())
        header.putInt(sampleRate)
        header.putInt(byteRate)
        header.putShort((channels * bitsPerSample / 8).toShort())
        header.putShort(bitsPerSample.toShort())
        // data subchunk
        header.put("data".toByteArray())
        header.putInt(dataLen)

        val out = java.io.ByteArrayOutputStream(44 + dataLen)
        out.write(header.array())
        out.write(pcmData, 0, dataLen)
        return out.toByteArray()
    }

    private fun sendAudioForAnalysis(wavBytes: ByteArray) {
        try {
            val body = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart(
                    "audio",
                    "chunk.wav",
                    RequestBody.create("audio/wav".toMediaType(), wavBytes)
                )
                .addFormDataPart("filter_profanity", filterProfanity.toString())
                .build()
            val req = Request.Builder()
                .url("http://10.0.2.2:8000/analyze-audio")
                .post(body)
                .build()
            client.newCall(req).execute().use { resp ->
                val bodyStr = resp.body?.string() ?: return
                if (!resp.isSuccessful) return
                handleAudioResponse(bodyStr)
            }
        } catch (_: Exception) {
            // ignore to keep loop alive
        }
    }

    private fun handleAudioResponse(json: String) {
        try {
            val obj = JSONObject(json)
            val transcript = obj.optString("transcribed_text", "")
            val pa = obj.optJSONObject("profanity_analysis") ?: return
            val action = pa.optString("action", "")
            if (action == "MUTE") {
                sendStatus("Audio: \"$transcript\" - MUTE APPLIED")
                applyTemporaryMute()
            } else {
                sendStatus("Audio: \"$transcript\" - ALLOW")
            }
        } catch (_: Exception) {
        }
    }

    private fun applyTemporaryMute() {
        val am = audioManager ?: return
        // Read current volume
        val stream = AudioManager.STREAM_MUSIC
        val original = am.getStreamVolume(stream)
        try {
            am.setStreamVolume(stream, 0, 0)
            Thread.sleep(1500) // BR-05: 1.5s mute
        } catch (_: Exception) {
        } finally {
            am.setStreamVolume(stream, original, 0)
        }
    }

    private fun sendStatus(message: String) {
        val ts = SimpleDateFormat("HH:mm:ss", Locale.US).format(Date())
        val intent = Intent("com.safeview.STATUS")
        intent.putExtra("message", "$ts - $message")
        sendBroadcast(intent)
    }
}

