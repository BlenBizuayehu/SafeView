package com.example.safeview_mobile

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import androidx.core.content.ContextCompat
import io.flutter.plugin.common.EventChannel
import android.content.BroadcastReceiver
import android.content.IntentFilter

class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.safeview/bridge"
    private val EVENTS = "com.safeview/bridge_events"
    private val REQ_OVERLAY = 1001
    private val REQ_MEDIA_PROJECTION = 1002
    private var pendingResult: MethodChannel.Result? = null
    private var pendingMethod: String? = null
    private var eventSink: EventChannel.EventSink? = null
    private var statusReceiver: BroadcastReceiver? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "checkOverlayPermission" -> {
                    val canDraw = Settings.canDrawOverlays(this)
                    result.success(canDraw)
                }
                "requestOverlayPermission" -> {
                    requestOverlayPermission(result)
                }
                "startProtection" -> {
                    // Expecting a map of settings from Flutter
                    val settings = call.arguments as? Map<*, *>
                    startMediaProjection(result, settings)
                }
                else -> result.notImplemented()
            }
        }
        EventChannel(flutterEngine.dartExecutor.binaryMessenger, EVENTS).setStreamHandler(object: EventChannel.StreamHandler {
            override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
                eventSink = events
                registerStatusReceiver()
            }
            override fun onCancel(arguments: Any?) {
                unregisterStatusReceiver()
                eventSink = null
            }
        })
    }

    private fun registerStatusReceiver() {
        if (statusReceiver != null) return
        statusReceiver = object: BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                if (intent?.action == "com.safeview.STATUS") {
                    val msg = intent.getStringExtra("message") ?: return
                    eventSink?.success(msg)
                }
            }
        }
        registerReceiver(statusReceiver, IntentFilter("com.safeview.STATUS"))
    }

    private fun unregisterStatusReceiver() {
        statusReceiver?.let { unregisterReceiver(it) }
        statusReceiver = null
    }

    private fun requestOverlayPermission(result: MethodChannel.Result) {
        if (Settings.canDrawOverlays(this)) {
            result.success(true)
            return
        }
        try {
            pendingResult = result
            pendingMethod = "requestOverlayPermission"
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:$packageName")
            )
            startActivityForResult(intent, REQ_OVERLAY)
        } catch (e: Exception) {
            result.error("overlay_intent_error", e.message, null)
        }
    }

    private var pendingSettings: Map<*, *>? = null

    private fun startMediaProjection(result: MethodChannel.Result, settings: Map<*, *>?) {
        try {
            pendingResult = result
            pendingMethod = "startProtection"
            pendingSettings = settings
            val mpm = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
            val intent = mpm.createScreenCaptureIntent()
            startActivityForResult(intent, REQ_MEDIA_PROJECTION)
        } catch (e: Exception) {
            result.error("media_projection_error", e.message, null)
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        val res = pendingResult ?: return
        val method = pendingMethod
        pendingResult = null
        pendingMethod = null

        when (requestCode) {
            REQ_OVERLAY -> {
                val granted = Settings.canDrawOverlays(this)
                res.success(granted)
            }
            REQ_MEDIA_PROJECTION -> {
                if (resultCode == Activity.RESULT_OK && data != null) {
                    // Start foreground service with projection extras
                    val svc = Intent(this, ScreenCaptureService::class.java).apply {
                        putExtra("resultCode", resultCode)
                        putExtra("dataIntent", data)
                        // Forward user settings as typed extras
                        val s = pendingSettings
                        val sensitivity = (s?.get("sensitivity") as? Number)?.toFloat() ?: 0.75f
                        val filterNudity = (s?.get("filter_nudity") as? Boolean) ?: true
                        val filterViolence = (s?.get("filter_violence") as? Boolean) ?: true
                        val filterProfanity = (s?.get("filter_profanity") as? Boolean) ?: true
                        val blockedThemes = (s?.get("blocked_themes") as? List<*>)?.mapNotNull { it as? String } ?: emptyList()
                        putExtra("sensitivity", sensitivity)
                        putExtra("filter_nudity", filterNudity)
                        putExtra("filter_violence", filterViolence)
                        putExtra("filter_profanity", filterProfanity)
                        putStringArrayListExtra("blocked_themes", ArrayList(blockedThemes))
                    }
                    ContextCompat.startForegroundService(this, svc)
                    res.success(true)
                } else {
                    res.success(false)
                }
            }
            else -> {
                res.success(false)
            }
        }
    }
}
