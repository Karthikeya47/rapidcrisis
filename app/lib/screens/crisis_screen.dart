/// crisis_screen.dart — Main crisis coordination screen
/// Press-to-talk → transcript → pipeline animation → dispatch card
library;

import 'dart:async';
import 'dart:math' as math;
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

class _CrisisScreenState extends State<CrisisScreen>
    with TickerProviderStateMixin {
  // Services
  final _stt = SttService();
  final _agent = CrisisAgentService();

  // State
  PipelineStep _step = PipelineStep.idle;
  String _transcript = '';
  String _statusMessage = 'Hold the button to speak a crisis command';
  CrisisResponse? _lastResponse;
  String? _errorMessage;
  bool _isBackendOnline = false;

  // Animation controllers
  late AnimationController _pulseController;
  late AnimationController _waveController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);
    _waveController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    );
    _checkBackend();
  }

  Future<void> _checkBackend() async {
    final online = await _agent.isBackendReachable();
    if (mounted) setState(() => _isBackendOnline = online);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _waveController.dispose();
    _stt.dispose();
    _agent.dispose();
    super.dispose();
  }

  // ── Crisis Pipeline ──────────────────────────────────────────
  Future<void> _startCrisisPipeline() async {
    if (_step != PipelineStep.idle && _step != PipelineStep.done && _step != PipelineStep.error) {
      return;
    }

    setState(() {
      _step = PipelineStep.recording;
      _transcript = '';
      _lastResponse = null;
      _errorMessage = null;
      _statusMessage = 'Listening for crisis command...';
    });
    _waveController.repeat();

    try {
      // Step 1: Record + transcribe
      final result = await _stt.recordAndTranscribe(
        durationSeconds: 5,
        onInterim: (partial) {
          if (mounted) setState(() => _statusMessage = partial);
        },
      );

      setState(() {
        _transcript = result.text;
        _step = PipelineStep.transcribing;
        _statusMessage = 'Transcript captured${result.isMock ? ' (demo)' : ''}';
      });
      _waveController.stop();
      _waveController.reset();

      await Future.delayed(const Duration(milliseconds: 600));

      // Step 2: Gemini thinking
      setState(() {
        _step = PipelineStep.thinking;
        _statusMessage = 'Gemini 1.5 Flash analyzing crisis...';
      });

      await Future.delayed(const Duration(milliseconds: 400));

      // Steps 3-4: Protocol + staff (handled in backend)
      setState(() {
        _step = PipelineStep.findingProtocol;
        _statusMessage = 'Fetching crisis protocol from Vertex AI...';
      });

      await Future.delayed(const Duration(milliseconds: 300));

      setState(() {
        _step = PipelineStep.findingStaff;
        _statusMessage = 'Querying on-shift staff from BigQuery...';
      });

      // Step 5: Submit to backend (orchestrates everything)
      final response = await _agent.submitCrisis(
        CrisisRequest(transcript: _transcript),
      );

      setState(() {
        _step = PipelineStep.dispatching;
        _statusMessage = 'Dispatching FCM alerts to ${response.staffDispatched.length} staff...';
      });

      await Future.delayed(const Duration(milliseconds: 500));

      setState(() {
        _step = PipelineStep.done;
        _lastResponse = response;
        _statusMessage = '✓ ${response.staffDispatched.length} staff alerted in ${response.responseMs}ms';
      });
    } catch (e) {
      setState(() {
        _step = PipelineStep.error;
        _errorMessage = e.toString().replaceFirst('Exception: ', '');
        _statusMessage = 'Pipeline failed';
      });
      _waveController.stop();
    }
  }

  void _reset() {
    setState(() {
      _step = PipelineStep.idle;
      _transcript = '';
      _statusMessage = 'Hold the button to speak a crisis command';
      _lastResponse = null;
      _errorMessage = null;
    });
  }

  // ── Build ────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      appBar: _buildAppBar(),
      body: SafeArea(
        child: Column(
          children: [
            // Status bar
            _BackendStatusBar(isOnline: _isBackendOnline),

            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Transcript display
                    if (_transcript.isNotEmpty)
                      _TranscriptCard(text: _transcript),

                    if (_transcript.isNotEmpty) const SizedBox(height: 16),

                    // Pipeline status
                    if (_step != PipelineStep.idle)
                      PipelineStatusWidget(currentStep: _step),

                    if (_step != PipelineStep.idle) const SizedBox(height: 16),

                    // Error
                    if (_errorMessage != null) _ErrorCard(message: _errorMessage!),

                    // Dispatch result
                    if (_lastResponse != null)
                      DispatchResultCard(response: _lastResponse!),

                    // Idle state hint cards
                    if (_step == PipelineStep.idle && _lastResponse == null)
                      _IdleHintPanel(),

                    const SizedBox(height: 120), // space for FAB
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: _BottomControls(
        step: _step,
        statusMessage: _statusMessage,
        pulseController: _pulseController,
        waveController: _waveController,
        onTap: _startCrisisPipeline,
        onReset: _reset,
      ),
    );
  }

  AppBar _buildAppBar() {
    return AppBar(
      backgroundColor: AppColors.bg,
      title: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: AppColors.critical,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(color: AppColors.critical.withOpacity(0.5), blurRadius: 6),
              ],
            ),
          )
              .animate()
              .fadeIn()
              .then()
              .fadeOut(duration: 800.ms)
              .then()
              .fadeIn(duration: 800.ms),
          const SizedBox(width: 10),
          Text('Crisis Response', style: AppTextStyles.heading),
        ],
      ),
      actions: [
        IconButton(
          onPressed: _checkBackend,
          icon: const Icon(Icons.refresh_rounded, size: 20),
          tooltip: 'Check backend',
        ),
        const SizedBox(width: 8),
      ],
    );
  }
}

// ── Sub-widgets ────────────────────────────────────────────────

class _BackendStatusBar extends StatelessWidget {
  final bool isOnline;
  const _BackendStatusBar({required this.isOnline});

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      height: 32,
      color: isOnline
          ? AppColors.accentGreen.withOpacity(0.08)
          : AppColors.critical.withOpacity(0.08),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              color: isOnline ? AppColors.accentGreen : AppColors.critical,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 6),
          Text(
            isOnline ? 'Backend online' : 'Backend offline — running in mock mode',
            style: AppTextStyles.caption.copyWith(
              color: isOnline ? AppColors.accentGreen : AppColors.critical,
            ),
          ),
        ],
      ),
    );
  }
}

class _TranscriptCard extends StatelessWidget {
  final String text;
  const _TranscriptCard({required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surfaceElevated,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.accent.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.mic, size: 14, color: AppColors.accent),
              const SizedBox(width: 6),
              Text('TRANSCRIPT', style: AppTextStyles.label.copyWith(color: AppColors.accent)),
            ],
          ),
          const SizedBox(height: 8),
          Text('"$text"',
              style: AppTextStyles.body.copyWith(
                  fontStyle: FontStyle.italic, fontSize: 15)),
        ],
      ),
    )
        .animate()
        .fadeIn(duration: 300.ms)
        .slideY(begin: -0.05, end: 0);
  }
}

class _ErrorCard extends StatelessWidget {
  final String message;
  const _ErrorCard({required this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: AppColors.criticalDim,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.critical.withOpacity(0.4)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: AppColors.critical, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(message,
                style: AppTextStyles.body.copyWith(color: AppColors.critical)),
          ),
        ],
      ),
    );
  }
}

class _IdleHintPanel extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final hints = [
      (Icons.mic_rounded, 'Speak', 'Say a crisis command like "2 trauma surgeons, Bay 4"'),
      (Icons.bolt_rounded, 'Instant', 'Gemini extracts crisis type, location, and staff needed'),
      (Icons.people_rounded, 'Match', 'On-shift staff queried from BigQuery in real time'),
      (Icons.notifications_active_rounded, 'Alert', 'FCM push sent directly to matched staff phones'),
    ];

    return Column(
      children: [
        const SizedBox(height: 24),
        Text('HOW IT WORKS', style: AppTextStyles.label),
        const SizedBox(height: 16),
        ...hints.asMap().entries.map((e) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _HintTile(
                icon: e.value.$1,
                title: e.value.$2,
                subtitle: e.value.$3,
                delay: e.key * 80,
              ),
            )),
      ],
    );
  }
}

class _HintTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final int delay;

  const _HintTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.delay,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surfaceElevated,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.accentDim,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: AppColors.accent, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: AppTextStyles.body.copyWith(fontWeight: FontWeight.w600)),
                Text(subtitle, style: AppTextStyles.caption),
              ],
            ),
          ),
        ],
      ),
    )
        .animate(delay: Duration(milliseconds: delay))
        .fadeIn(duration: 400.ms)
        .slideX(begin: 0.04, end: 0);
  }
}

class _BottomControls extends StatelessWidget {
  final PipelineStep step;
  final String statusMessage;
  final AnimationController pulseController;
  final AnimationController waveController;
  final VoidCallback onTap;
  final VoidCallback onReset;

  const _BottomControls({
    required this.step,
    required this.statusMessage,
    required this.pulseController,
    required this.waveController,
    required this.onTap,
    required this.onReset,
  });

  @override
  Widget build(BuildContext context) {
    final isIdle = step == PipelineStep.idle ||
        step == PipelineStep.done ||
        step == PipelineStep.error;
    final isRecording = step == PipelineStep.recording;
    final isProcessing = !isIdle && !isRecording;

    return Container(
      padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(top: BorderSide(color: AppColors.border)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Status message
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 300),
            child: Text(
              statusMessage,
              key: ValueKey(statusMessage),
              style: AppTextStyles.caption,
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: 16),
          // Action buttons
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (step == PipelineStep.done || step == PipelineStep.error)
                Padding(
                  padding: const EdgeInsets.only(right: 16),
                  child: GestureDetector(
                    onTap: onReset,
                    child: Container(
                      width: 52,
                      height: 52,
                      decoration: BoxDecoration(
                        color: AppColors.surfaceElevated,
                        shape: BoxShape.circle,
                        border: Border.all(color: AppColors.border, width: 1.5),
                      ),
                      child: const Icon(Icons.refresh_rounded,
                          color: AppColors.textSecondary, size: 22),
                    ),
                  ),
                ),
              // Main record button
              _RecordButton(
                step: step,
                pulseController: pulseController,
                waveController: waveController,
                onTap: isIdle ? onTap : null,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _RecordButton extends StatelessWidget {
  final PipelineStep step;
  final AnimationController pulseController;
  final AnimationController waveController;
  final VoidCallback? onTap;

  const _RecordButton({
    required this.step,
    required this.pulseController,
    required this.waveController,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final isRecording = step == PipelineStep.recording;
    final isDone = step == PipelineStep.done;
    final isProcessing = !isRecording && !isDone &&
        step != PipelineStep.idle && step != PipelineStep.error;

    final color = isDone
        ? AppColors.accentGreen
        : isRecording
            ? AppColors.critical
            : AppColors.accent;

    return GestureDetector(
      onTap: onTap,
      child: AnimatedBuilder(
        animation: pulseController,
        builder: (context, child) {
          final pulse = isRecording
              ? 1.0 + (pulseController.value * 0.15)
              : 1.0;

          return Stack(
            alignment: Alignment.center,
            children: [
              // Outer glow ring
              if (isRecording)
                Container(
                  width: 88 * pulse,
                  height: 88 * pulse,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: color.withOpacity(0.3 * (1 - pulseController.value)),
                      width: 2,
                    ),
                  ),
                ),
              // Button
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: color.withOpacity(0.15),
                  border: Border.all(color: color, width: 2),
                  boxShadow: [
                    BoxShadow(
                      color: color.withOpacity(0.3),
                      blurRadius: 20,
                      spreadRadius: isRecording ? 4 : 0,
                    ),
                  ],
                ),
                child: isProcessing
                    ? const _SpinnerIcon()
                    : Icon(
                        isDone
                            ? Icons.check_rounded
                            : isRecording
                                ? Icons.stop_rounded
                                : Icons.mic_rounded,
                        color: color,
                        size: 30,
                      ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _SpinnerIcon extends StatefulWidget {
  const _SpinnerIcon();

  @override
  State<_SpinnerIcon> createState() => _SpinnerIconState();
}

class _SpinnerIconState extends State<_SpinnerIcon>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) => Transform.rotate(
        angle: _ctrl.value * 2 * math.pi,
        child: const Icon(Icons.autorenew_rounded,
            color: AppColors.accent, size: 28),
      ),
    );
  }
}
