/// crisis_screen.dart — Optimized for v2 Streaming + Agentic Backend
library;

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../models/crisis_request.dart';
import '../services/stt_service.dart';
import '../services/crisis_agent_service.dart';
import '../theme.dart';
import '../widgets/pipeline_status.dart';
import '../widgets/dispatch_card.dart';

class CrisisScreen extends StatefulWidget {
  const CrisisScreen({super.key});

  @override
  State<CrisisScreen> createState() => _CrisisScreenState();
}

class _CrisisScreenState extends State<CrisisScreen> with TickerProviderStateMixin {
  final _stt = SttService();
  final _agent = CrisisAgentService();

  PipelineStep _step = PipelineStep.idle;
  String _transcript = '';
  String _statusMessage = 'Hold to activate Crisis Pipeline';
  CrisisResponse? _lastResponse;
  String? _errorMessage;
  bool _isBackendOnline = false;

  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    )..repeat(reverse: true);
    _checkBackend();
  }

  Future<void> _checkBackend() async {
    final online = await _agent.isBackendReachable();
    if (mounted) setState(() => _isBackendOnline = online);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _stt.dispose();
    _agent.dispose();
    super.dispose();
  }

  Future<void> _startCrisisPipeline() async {
    if (_step != PipelineStep.idle && _step != PipelineStep.done && _step != PipelineStep.error) return;

    setState(() {
      _step = PipelineStep.recording;
      _transcript = '';
      _lastResponse = null;
      _errorMessage = null;
      _statusMessage = 'Listening...';
    });

    try {
      // Step 1: STT v2 Streaming
      final result = await _stt.recordAndTranscribe(
        durationSeconds: 5,
        onInterim: (partial) {
          if (mounted) setState(() => _transcript = partial);
        },
      );

      // Step 2-5: Multi-pass Backend (Agentic Flow)
      setState(() {
        _transcript = result.text;
        _step = PipelineStep.thinking;
        _statusMessage = 'Agentic Pipeline active...';
      });

      final response = await _agent.submitCrisis(CrisisRequest(transcript: _transcript));

      setState(() {
        _step = PipelineStep.done;
        _lastResponse = response;
        _statusMessage = 'Dispatch Complete';
      });
    } catch (e) {
      setState(() {
        _step = PipelineStep.error;
        _errorMessage = e.toString();
        _statusMessage = 'Pipeline failed';
      });
    }
  }

  void _reset() {
    setState(() {
      _step = PipelineStep.idle;
      _transcript = '';
      _statusMessage = 'Hold to activate Crisis Pipeline';
      _lastResponse = null;
      _errorMessage = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: AppBar(
        title: Text('RAPID CRISIS', style: AppTextStyles.heading.copyWith(letterSpacing: 1.5)),
        actions: [
          IconButton(onPressed: _checkBackend, icon: const Icon(Icons.hub_outlined, size: 20)),
          const SizedBox(width: 8),
        ],
      ),
      body: Stack(
        children: [
          // Background Glow
          Positioned(
            top: -100,
            right: -100,
            child: Container(
              width: 300,
              height: 300,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _step == PipelineStep.recording ? AppColors.critical.withOpacity(0.05) : AppColors.accent.withOpacity(0.05),
              ),
            ).animate(onPlay: (c) => c.repeat()).blur(begin: const Offset(80, 80), end: const Offset(120, 120), duration: 4.seconds),
          ),

          SafeArea(
            child: CustomScrollView(
              physics: const BouncingScrollPhysics(),
              slivers: [
                SliverPadding(
                  padding: const EdgeInsets.all(20),
                  sliver: SliverList(
                    delegate: SliverChildListDelegate([
                      if (_transcript.isNotEmpty || _step == PipelineStep.recording)
                        _TranscriptPanel(text: _transcript, isRecording: _step == PipelineStep.recording),

                      const SizedBox(height: 24),

                      if (_step != PipelineStep.idle)
                        PipelineStatusWidget(currentStep: _step).animate().fadeIn().slideY(begin: 0.1, end: 0),

                      if (_lastResponse != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 24),
                          child: DispatchResultCard(response: _lastResponse!).animate().scale(delay: 200.ms),
                        ),

                      if (_errorMessage != null)
                        _ErrorPanel(message: _errorMessage!),

                      if (_step == PipelineStep.idle && _lastResponse == null)
                        _OnboardingPanel(),

                      const SizedBox(height: 140),
                    ]),
                  ),
                ),
              ],
            ),
          ),

          // Floating Action Area
          Align(
            alignment: Alignment.bottomCenter,
            child: _MainActionTray(
              step: _step,
              status: _statusMessage,
              onTap: _startCrisisPipeline,
              onReset: _reset,
              pulse: _pulseController,
            ),
          ),
        ],
      ),
    );
  }
}

class _TranscriptPanel extends StatelessWidget {
  final String text;
  final bool isRecording;
  const _TranscriptPanel({required this.text, required this.isRecording});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surfaceElevated,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: isRecording ? AppColors.critical.withOpacity(0.3) : AppColors.border),
        boxShadow: [
          if (isRecording) BoxShadow(color: AppColors.critical.withOpacity(0.1), blurRadius: 20, spreadRadius: 2),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(isRecording ? Icons.fiber_manual_record : Icons.notes, size: 14, color: isRecording ? AppColors.critical : AppColors.accent),
              const SizedBox(width: 8),
              Text(isRecording ? 'LIVE TRANSCRIPT' : 'REQUEST', style: AppTextStyles.label.copyWith(color: isRecording ? AppColors.critical : AppColors.accent)),
              const Spacer(),
              if (isRecording)
                const Text('v2 STREAMING', style: TextStyle(fontSize: 8, color: AppColors.textMuted, fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            text.isEmpty ? (isRecording ? "Listening..." : "...") : text,
            style: AppTextStyles.displayLarge.copyWith(fontSize: 22, height: 1.3),
          ),
        ],
      ),
    );
  }
}

class _OnboardingPanel extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const SizedBox(height: 40),
        Icon(Icons.emergency_outlined, size: 64, color: AppColors.textMuted.withOpacity(0.2)),
        const SizedBox(height: 16),
        Text('Ready for Dispatch', style: AppTextStyles.heading.copyWith(color: AppColors.textMuted)),
        const SizedBox(height: 8),
        Text('Hold the button below to initiate emergency protocols', style: AppTextStyles.body.copyWith(color: AppColors.textMuted), textAlign: TextAlign.center),
      ],
    ).animate().fadeIn(delay: 300.ms);
  }
}

class _ErrorPanel extends StatelessWidget {
  final String message;
  const _ErrorPanel({required this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 24),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: AppColors.critical.withOpacity(0.1), borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.critical.withOpacity(0.2))),
      child: Text(message, style: AppTextStyles.body.copyWith(color: AppColors.critical)),
    );
  }
}

class _MainActionTray extends StatelessWidget {
  final PipelineStep step;
  final String status;
  final VoidCallback onTap;
  final VoidCallback onReset;
  final AnimationController pulse;

  const _MainActionTray({required this.step, required this.status, required this.onTap, required this.onReset, required this.pulse});

  @override
  Widget build(BuildContext context) {
    final isRecording = step == PipelineStep.recording;
    final isIdle = step == PipelineStep.idle || step == PipelineStep.done || step == PipelineStep.error;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [AppColors.bg.withOpacity(0), AppColors.bg, AppColors.bg],
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(status.toUpperCase(), style: AppTextStyles.label.copyWith(color: isRecording ? AppColors.critical : AppColors.textMuted)),
          const SizedBox(height: 20),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (step == PipelineStep.done || step == PipelineStep.error)
                IconButton(onPressed: onReset, icon: const Icon(Icons.refresh, color: AppColors.textMuted)).animate().scale(),

              const SizedBox(width: 16),

              GestureDetector(
                onTap: isIdle ? onTap : null,
                child: AnimatedBuilder(
                  animation: pulse,
                  builder: (context, child) {
                    return Container(
                      width: 80,
                      height: 80,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: isRecording ? AppColors.critical : AppColors.accent,
                        boxShadow: [
                          BoxShadow(
                            color: (isRecording ? AppColors.critical : AppColors.accent).withOpacity(0.4 * (1 - pulse.value)),
                            blurRadius: 20 * pulse.value,
                            spreadRadius: 10 * pulse.value,
                          ),
                        ],
                      ),
                      child: Icon(
                        isRecording ? Icons.mic : (step == PipelineStep.done ? Icons.check : Icons.mic_none),
                        color: Colors.black,
                        size: 32,
                      ),
                    );
                  },
                ),
              ),

              const SizedBox(width: 68), // Spacer to balance reset button
            ],
          ),
        ],
      ),
    );
  }
}
