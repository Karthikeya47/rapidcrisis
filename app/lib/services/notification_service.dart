/// notification_service.dart — FCM listener for incoming crisis alerts
library;

import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

/// Background message handler — must be a top-level function
@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  debugPrint('[FCM Background] ${message.messageId}: ${message.notification?.title}');
}

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  final FirebaseMessaging _fcm = FirebaseMessaging.instance;
  String? _deviceToken;

  final _alertController = StreamController<CrisisAlert>.broadcast();
  Stream<CrisisAlert> get alerts => _alertController.stream;

  String? get deviceToken => _deviceToken;

  /// Initialize FCM — call once from main()
  Future<void> initialize() async {
    // Register background handler
    FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

    // Request notification permission (Android 13+)
    final settings = await _fcm.requestPermission(
      alert: true,
      badge: true,
      sound: true,
      criticalAlert: true,
    );
    debugPrint('[FCM] Permission: ${settings.authorizationStatus}');

    // Get device token for this device
    _deviceToken = await _fcm.getToken();
    debugPrint('[FCM] Device token: $_deviceToken');

    // Show notifications while app is in foreground
    await _fcm.setForegroundNotificationPresentationOptions(
      alert: true,
      badge: true,
      sound: true,
    );

    // Foreground message listener
    FirebaseMessaging.onMessage.listen((message) {
      debugPrint('[FCM Foreground] ${message.notification?.title}');
      final alert = CrisisAlert.fromRemoteMessage(message);
      _alertController.add(alert);
    });

    // Tapped notification that opened the app
    FirebaseMessaging.onMessageOpenedApp.listen((message) {
      debugPrint('[FCM Opened] ${message.notification?.title}');
    });
  }

  void dispose() {
    _alertController.close();
  }
}

class CrisisAlert {
  final String title;
  final String body;
  final String crisisType;
  final String location;
  final String urgency;

  const CrisisAlert({
    required this.title,
    required this.body,
    required this.crisisType,
    required this.location,
    required this.urgency,
  });

  factory CrisisAlert.fromRemoteMessage(RemoteMessage message) {
    final data = message.data;
    return CrisisAlert(
      title: message.notification?.title ?? 'Crisis Alert',
      body: message.notification?.body ?? '',
      crisisType: data['crisis_type'] ?? 'unknown',
      location: data['location'] ?? '',
      urgency: data['urgency'] ?? 'high',
    );
  }
}
