/// stt_service.dart — Cloud Speech-to-Text v2 STREAMING implementation
/// Streams audio chunks directly to Google Cloud for near-zero latency.
library;

import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:google_speech/google_speech.dart';
import 'package:record/record.dart';
import 'package:permission_handler/permission_handler.dart';

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
  StreamSubscription<List<int>>? _audioStreamSubscription;

  SttService({String? apiKey}) : _apiKey = apiKey;

  Future<bool> requestPermission() async {
    final status = await Permission.microphone.request();
    return status.isGranted;
  }

  /// Streams audio to Cloud STT v2 and provides real-time transcript updates.
  Future<TranscriptResult> recordAndTranscribe({
    int durationSeconds = 6,
    void Function(String partial)? onInterim,
  }) async {
    if (_apiKey == null || _apiKey!.isEmpty) {
      return _mockStreaming(durationSeconds, onInterim);
    }

    final hasPermission = await requestPermission();
    if (!hasPermission) throw Exception('Microphone permission denied');

    final serviceAccount = ServiceAccount.fromApiKey(_apiKey!);
    final speechToText = SpeechToText.viaServiceAccount(serviceAccount);

    final config = RecognitionConfig(
      encoding: AudioEncoding.LINEAR16,
      model: RecognitionModel.latest_short,
      enableAutomaticPunctuation: true,
      sampleRateHertz: 16000,
      languageCode: 'en-US',
    );

    final streamingConfig = StreamingRecognitionConfig(
      config: config,
      interimResults: true,
    );

    final audioStream = await _recorder.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
      ),
    );

    final responseStream = speechToText.streamingRecognize(
      streamingConfig,
      audioStream.map((data) => data as List<int>),
    );

    String finalTranscript = '';
    final completer = Completer<TranscriptResult>();

    responseStream.listen((data) {
      for (var result in data.results) {
        final transcript = result.alternatives.first.transcript;
        if (result.isFinal) {
          finalTranscript = transcript;
          onInterim?.call(finalTranscript);
        } else {
          onInterim?.call('$finalTranscript $transcript'.strip());
        }
      }
    }, onDone: () {
      if (!completer.isCompleted) {
        completer.complete(TranscriptResult(text: finalTranscript, confidence: 0.9));
      }
    }, onError: (e) {
      debugPrint('[STT] Stream Error: $e');
      if (!completer.isCompleted) completer.complete(_mockTranscript());
    });

    // Stop recording after duration
    Future.delayed(Duration(seconds: durationSeconds), () async {
      await _recorder.stop();
      if (!completer.isCompleted) {
        completer.complete(TranscriptResult(text: finalTranscript, confidence: 0.9));
      }
    });

    return completer.future;
  }

  Future<TranscriptResult> _mockStreaming(int duration, Function(String)? onInterim) async {
    final mock = _mockTranscript();
    final words = mock.text.split(' ');
    for (int i = 0; i < words.length; i++) {
      await Future.delayed(const Duration(milliseconds: 400));
      onInterim?.call(words.sublist(0, i + 1).join(' '));
    }
    return mock;
  }

  TranscriptResult _mockTranscript() {
    final samples = [
      'Need two trauma surgeons stat, Bay 4, patient is coding',
      'Code blue in ICU Room 7, cardiac arrest, need cardiologist now',
      'Three nurses to floor 5, mass casualty incoming',
    ];
    return TranscriptResult(
      text: samples[DateTime.now().second % samples.length],
      confidence: 0.95,
      isMock: true,
    );
  }

  void dispose() {
    _audioStreamSubscription?.cancel();
    _recorder.dispose();
  }
}

extension StringExtension on String {
  String strip() => trim();
}
