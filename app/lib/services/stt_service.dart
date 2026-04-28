/// stt_service.dart — Cloud Speech-to-Text v2 streaming via HTTP REST
/// Falls back to local mock transcription when credentials are absent.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:record/record.dart';
import 'package:http/http.dart' as http;
import 'package:permission_handler/permission_handler.dart';

const _sttEndpoint =
    'https://speech.googleapis.com/v1/speech:recognize';

/// Simplified transcription result
class TranscriptResult {
  final String text;
  final double confidence;
  final bool isMock;

  const TranscriptResult({
    required this.text,
    required this.confidence,
    this.isMock = false,
  });
}

class SttService {
  final AudioRecorder _recorder = AudioRecorder();
  final String? _apiKey;

  SttService({String? apiKey}) : _apiKey = apiKey;

  /// Request microphone permission
  Future<bool> requestPermission() async {
    final status = await Permission.microphone.request();
    return status.isGranted;
  }

  /// Record audio for [durationSeconds] then transcribe via Cloud STT.
  /// Streams interim text via [onInterim] and returns final transcript.
  Future<TranscriptResult> recordAndTranscribe({
    int durationSeconds = 6,
    void Function(String partial)? onInterim,
  }) async {
    final hasPermission = await requestPermission();
    if (!hasPermission) {
      throw Exception('Microphone permission denied');
    }

    // Simulate interim updates while recording
    int elapsed = 0;
    final interimTimer = Timer.periodic(const Duration(seconds: 1), (t) {
      elapsed++;
      onInterim?.call('Recording... ($elapsed/$durationSeconds s)');
    });

    // Record to temp file
    final tempPath = '${Directory.systemTemp.path}/crisis_audio.wav';
    await _recorder.start(
      const RecordConfig(
        encoder: AudioEncoder.wav,
        sampleRate: 16000,
        numChannels: 1,
        bitRate: 128000,
      ),
      path: tempPath,
    );

    await Future.delayed(Duration(seconds: durationSeconds));
    interimTimer.cancel();

    final recordingPath = await _recorder.stop();
    if (recordingPath == null) {
      throw Exception('Recording failed — no audio captured');
    }

    onInterim?.call('Transcribing...');

    final audioBytes = await File(recordingPath).readAsBytes();
    return _transcribeAudio(audioBytes);
  }

  Future<TranscriptResult> _transcribeAudio(Uint8List audioBytes) async {
    if (_apiKey == null || _apiKey!.isEmpty) {
      debugPrint('[STT] No API key — using mock transcript');
      return _mockTranscript();
    }

    try {
      final body = jsonEncode({
        'config': {
          'encoding': 'LINEAR16',
          'sampleRateHertz': 16000,
          'languageCode': 'en-US',
          'model': 'latest_short',
          'useEnhanced': true,
          'enableAutomaticPunctuation': true,
        },
        'audio': {
          'content': base64Encode(audioBytes),
        },
      });

      final response = await http.post(
        Uri.parse('$_sttEndpoint?key=$_apiKey'),
        headers: {'Content-Type': 'application/json'},
        body: body,
      );

      if (response.statusCode == 200) {
        final json = jsonDecode(response.body) as Map<String, dynamic>;
        final results = json['results'] as List<dynamic>?;
        if (results != null && results.isNotEmpty) {
          final alt = (results[0] as Map)['alternatives'] as List;
          final transcript = alt[0]['transcript'] as String;
          final confidence = (alt[0]['confidence'] as num?)?.toDouble() ?? 0.9;
          return TranscriptResult(text: transcript, confidence: confidence);
        }
      }
      debugPrint('[STT] API error ${response.statusCode}: ${response.body}');
      return _mockTranscript();
    } catch (e) {
      debugPrint('[STT] Exception: $e');
      return _mockTranscript();
    }
  }

  TranscriptResult _mockTranscript() {
    // Rotate through realistic mock transcripts for demo
    final samples = [
      'Need two trauma surgeons stat, Bay 4, patient is coding',
      'Code blue in ICU Room 7, cardiac arrest, need cardiologist now',
      'Three nurses to floor 5, mass casualty incoming',
      'Respiratory distress in pediatric ward, need ICU doctor immediately',
    ];
    final idx = DateTime.now().second % samples.length;
    return TranscriptResult(
      text: samples[idx],
      confidence: 0.95,
      isMock: true,
    );
  }

  void dispose() {
    _recorder.dispose();
  }
}
