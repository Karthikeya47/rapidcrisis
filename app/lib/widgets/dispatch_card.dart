/// dispatch_card.dart — Displays crisis dispatch result
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../models/crisis_request.dart';
import '../theme.dart';

class DispatchResultCard extends StatelessWidget {
  final CrisisResponse response;

  const DispatchResultCard({super.key, required this.response});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _UrgencyBanner(urgency: response.urgency, crisisType: response.crisisType),
        const SizedBox(height: 12),
        _SummaryCard(response: response),
        const SizedBox(height: 12),
        _ProtocolCard(protocol: response.protocol),
        const SizedBox(height: 12),
        _StaffDispatchCard(staff: response.staffDispatched, fcmSent: response.fcmSent),
        const SizedBox(height: 12),
        _MetaRow(response: response),
      ],
    )
        .animate()
        .fadeIn(duration: 400.ms)
        .slideY(begin: 0.1, end: 0, duration: 400.ms, curve: Curves.easeOut);
  }
}

class _UrgencyBanner extends StatelessWidget {
  final UrgencyLevel urgency;
  final String crisisType;

  const _UrgencyBanner({required this.urgency, required this.crisisType});

  @override
  Widget build(BuildContext context) {
    final (color, bgColor, emoji) = switch (urgency) {
      UrgencyLevel.critical => (AppColors.critical, AppColors.criticalDim, '🚨'),
      UrgencyLevel.high => (AppColors.high, AppColors.highDim, '⚠️'),
      UrgencyLevel.medium => (AppColors.medium, AppColors.mediumDim, '📢'),
      UrgencyLevel.unknown => (AppColors.accent, AppColors.accentDim, '📡'),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.5)),
      ),
      child: Row(
        children: [
          Text(emoji, style: const TextStyle(fontSize: 22)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${crisisType.replaceAll('_', ' ').toUpperCase()} — ${urgency.label}',
                  style: AppTextStyles.heading.copyWith(color: color),
                ),
                Text(
                  'CRISIS RESPONSE DISPATCHED',
                  style: AppTextStyles.label.copyWith(color: color.withOpacity(0.7)),
                ),
              ],
            ),
          ),
          Icon(Icons.check_circle_rounded, color: color, size: 28),
        ],
      ),
    )
        .animate()
        .shimmer(duration: 1200.ms, color: color.withOpacity(0.2));
  }
}

class _SummaryCard extends StatelessWidget {
  final CrisisResponse response;
  const _SummaryCard({required this.response});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('SITUATION', style: AppTextStyles.label),
            const SizedBox(height: 8),
            Text(response.summary, style: AppTextStyles.body),
            const SizedBox(height: 12),
            Row(
              children: [
                _InfoChip(label: '📍', value: response.location),
                const SizedBox(width: 8),
                _InfoChip(label: '🏥', value: response.crisisType.replaceAll('_', ' ')),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ProtocolCard extends StatelessWidget {
  final ProtocolInfo protocol;
  const _ProtocolCard({required this.protocol});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('PROTOCOL', style: AppTextStyles.label),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.accentDim,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: AppColors.accent.withOpacity(0.3)),
                  ),
                  child: Text(
                    protocol.code,
                    style: AppTextStyles.mono.copyWith(color: AppColors.accent),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(protocol.name, style: AppTextStyles.heading.copyWith(fontSize: 15)),
            const SizedBox(height: 12),
            ...protocol.steps.asMap().entries.map((e) => Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 20,
                        height: 20,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: AppColors.accentGreenDim,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          '${e.key + 1}',
                          style: AppTextStyles.caption.copyWith(
                            color: AppColors.accentGreen,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(e.value,
                            style: AppTextStyles.body.copyWith(fontSize: 13)),
                      ),
                    ],
                  ),
                )),
          ],
        ),
      ),
    );
  }
}

class _StaffDispatchCard extends StatelessWidget {
  final List<StaffInfo> staff;
  final bool fcmSent;

  const _StaffDispatchCard({required this.staff, required this.fcmSent});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text('DISPATCHED STAFF', style: AppTextStyles.label),
                const Spacer(),
                if (fcmSent)
                  Row(
                    children: [
                      const Icon(Icons.notifications_active,
                          size: 14, color: AppColors.accentGreen),
                      const SizedBox(width: 4),
                      Text(
                        'FCM SENT',
                        style: AppTextStyles.label
                            .copyWith(color: AppColors.accentGreen),
                      ),
                    ],
                  ),
              ],
            ),
            const SizedBox(height: 12),
            ...staff.asMap().entries.map((e) => _StaffRow(
                  staff: e.value,
                  delay: e.key * 100,
                )),
          ],
        ),
      ),
    );
  }
}

class _StaffRow extends StatelessWidget {
  final StaffInfo staff;
  final int delay;

  const _StaffRow({required this.staff, required this.delay});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          CircleAvatar(
            radius: 18,
            backgroundColor: AppColors.accentDim,
            child: Text(
              staff.name.substring(staff.name.lastIndexOf(' ') + 1)[0],
              style: AppTextStyles.body
                  .copyWith(color: AppColors.accent, fontWeight: FontWeight.w700),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(staff.name,
                    style: AppTextStyles.body
                        .copyWith(fontWeight: FontWeight.w500)),
                Text('${staff.roleDisplay} • ${staff.department}',
                    style: AppTextStyles.caption),
              ],
            ),
          ),
          const Icon(Icons.phone_in_talk_rounded,
              size: 18, color: AppColors.accentGreen),
        ],
      ),
    )
        .animate(delay: Duration(milliseconds: delay))
        .fadeIn(duration: 300.ms)
        .slideX(begin: 0.05, end: 0);
  }
}

class _MetaRow extends StatelessWidget {
  final CrisisResponse response;
  const _MetaRow({required this.response});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        _InfoChip(
          label: '⏱',
          value: '${response.responseMs}ms',
        ),
        const SizedBox(width: 8),
        _InfoChip(
          label: '🆔',
          value: response.eventId.substring(0, 8),
        ),
        const SizedBox(width: 8),
        _InfoChip(
          label: '📡',
          value: response.dispatchMode.toUpperCase(),
        ),
      ],
    );
  }
}

class _InfoChip extends StatelessWidget {
  final String label;
  final String value;

  const _InfoChip({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: const TextStyle(fontSize: 11)),
          const SizedBox(width: 4),
          Text(value, style: AppTextStyles.caption),
        ],
      ),
    );
  }
}
