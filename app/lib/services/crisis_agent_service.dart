/// crisis_agent_service.dart — Calls Cloud Run backend /crisis endpoint
library;

import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../models/crisis_request.dart';

/// Replace with your Cloud Run URL after deployment:
/// gcloud run deploy crisis-agent → get the URL
const _backendBaseUrl = String.fromEnvironment(
  'BACKEND_URL',
  defaultValue: 'https://crisis-agent-1051430206062.asia-south1.run.app', // Cloud Run backend
);

class CrisisAgentService {
  final String baseUrl;
  final http.Client _client;

  CrisisAgentService({
    String? baseUrl,
    http.Client? client,
  })  : baseUrl = baseUrl ?? _backendBaseUrl,
        _client = client ?? http.Client();

  /// Submit a transcript and run the full crisis pipeline.
  Future<CrisisResponse> submitCrisis(CrisisRequest request) async {
    final uri = Uri.parse('$baseUrl/crisis');

    debugPrint('[CrisisAgent] POST $uri | transcript: "${request.transcript}"');

    final response = await _client
        .post(
          uri,
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          body: jsonEncode(request.toJson()),
        )
        .timeout(const Duration(seconds: 30));

    debugPrint('[CrisisAgent] Response ${response.statusCode}: ${response.body.substring(0, response.body.length.clamp(0, 200))}');

    if (response.statusCode == 200) {
      final json = jsonDecode(response.body) as Map<String, dynamic>;
      return CrisisResponse.fromJson(json);
    } else {
      final error = _parseError(response.body);
      throw CrisisApiException(
        statusCode: response.statusCode,
        message: error,
      );
    }
  }

  /// Health check — ping backend
  Future<bool> isBackendReachable() async {
    try {
      final response = await _client
          .get(Uri.parse('$baseUrl/health'))
          .timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  String _parseError(String body) {
    try {
      final json = jsonDecode(body) as Map<String, dynamic>;
      return json['detail'] as String? ?? 'Unknown error';
    } catch (_) {
      return body.isEmpty ? 'No response from server' : body;
    }
  }

  void dispose() {
    _client.close();
  }
}

class CrisisApiException implements Exception {
  final int statusCode;
  final String message;
  const CrisisApiException({required this.statusCode, required this.message});

  @override
  String toString() => 'CrisisApiException($statusCode): $message';
}
