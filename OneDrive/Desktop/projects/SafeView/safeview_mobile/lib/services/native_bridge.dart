import 'package:flutter/services.dart';

class NativeBridge {
  static const MethodChannel _channel = MethodChannel('com.safeview/bridge');
  static const EventChannel _events = EventChannel('com.safeview/bridge_events');

  static Future<bool> checkOverlayPermission() async {
    try {
      final result = await _channel.invokeMethod<bool>('checkOverlayPermission');
      return result ?? false;
    } on PlatformException {
      return false;
    }
  }

  static Future<bool> requestOverlayPermission() async {
    try {
      final result = await _channel.invokeMethod<bool>('requestOverlayPermission');
      return result ?? false;
    } on PlatformException {
      return false;
    }
  }

  static Future<bool> startProtection(Map<String, dynamic> settings) async {
    try {
      final result = await _channel.invokeMethod<bool>('startProtection', settings);
      return result ?? false;
    } on PlatformException {
      return false;
    }
  }

  static Stream<dynamic> statusStream() {
    return _events.receiveBroadcastStream();
  }
}
