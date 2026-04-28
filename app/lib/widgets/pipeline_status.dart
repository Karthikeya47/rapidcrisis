/// pipeline_status.dart — Animated pipeline step tracker widget
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../models/crisis_request.dart';
import '../theme.dart';

class PipelineStatusWidget extends StatelessWidget {
  final PipelineStep currentStep;

  const PipelineStatusWidget({super.key, required this.currentStep});

  static const _steps = [
    PipelineStep.recording,
    PipelineStep.transcribing,
    PipelineStep.thinking,
    PipelineStep.findingProtocol,
    PipelineStep.findingStaff,
    PipelineStep.dispatching,
    PipelineStep.done,
  ];

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surfaceElevated,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('PIPELINE', style: AppTextStyles.label),
          const SizedBox(height: 16),
          ..._steps.asMap().entries.map((entry) {
            final step = entry.value;
            final state = _stepState(step);
            return _StepRow(
              step: step,
              state: state,
              isLast: entry.key == _steps.length - 1,
            );
          }),
        ],
      ),
    );
  }

  _StepState _stepState(PipelineStep step) {
    if (currentStep == PipelineStep.idle || currentStep == PipelineStep.error) {
      return _StepState.pending;
    }
    if (currentStep == step) return _StepState.active;
    if (currentStep == PipelineStep.done) return _StepState.done;
    final curIdx = _steps.indexOf(currentStep);
    final stepIdx = _steps.indexOf(step);
    if (stepIdx < curIdx) return _StepState.done;
    return _StepState.pending;
  }
}

enum _StepState { pending, active, done }

class _StepRow extends StatelessWidget {
  final PipelineStep step;
  final _StepState state;
  final bool isLast;

  const _StepRow({
    required this.step,
    required this.state,
    required this.isLast,
  });

  @override
  Widget build(BuildContext context) {
    final color = switch (state) {
      _StepState.active => AppColors.accent,
      _StepState.done => AppColors.accentGreen,
      _StepState.pending => AppColors.textMuted,
    };

    final icon = switch (state) {
      _StepState.active => Icons.radio_button_on,
      _StepState.done => Icons.check_circle_rounded,
      _StepState.pending => Icons.radio_button_off,
    };

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Icon column with connector line
          SizedBox(
            width: 24,
            child: Column(
              children: [
                Icon(icon, size: 18, color: color)
                    .animate(target: state == _StepState.active ? 1 : 0)
                    .scaleXY(begin: 1, end: 1.2, duration: 600.ms)
                    .then()
                    .scaleXY(end: 1, duration: 600.ms),
                if (!isLast)
                  Expanded(
                    child: Container(
                      width: 2,
                      margin: const EdgeInsets.symmetric(vertical: 2),
                      decoration: BoxDecoration(
                        color: state == _StepState.done
                            ? AppColors.accentGreen.withOpacity(0.4)
                            : AppColors.textMuted.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(1),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          // Step label
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: isLast ? 0 : 14),
              child: Text(
                step.label,
                style: AppTextStyles.body.copyWith(
                  color: state == _StepState.pending
                      ? AppColors.textMuted
                      : state == _StepState.active
                          ? AppColors.accent
                          : AppColors.accentGreen,
                  fontWeight: state == _StepState.active
                      ? FontWeight.w600
                      : FontWeight.w400,
                ),
              )
                  .animate(target: state == _StepState.active ? 1 : 0)
                  .fadeIn(duration: 300.ms),
            ),
          ),
        ],
      ),
    );
  }
}
