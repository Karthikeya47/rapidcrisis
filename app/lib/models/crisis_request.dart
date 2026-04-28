/// crisis_request.dart — Data models for crisis pipeline
library;

class CrisisRequest {
  final String transcript;
  final String? callerId;
  final String? locationHint;

  const CrisisRequest({
    required this.transcript,
    this.callerId,
    this.locationHint,
  });

  Map<String, dynamic> toJson() => {
        'transcript': transcript,
        if (callerId != null) 'caller_id': callerId,
        if (locationHint != null) 'location_hint': locationHint,
      };
}

class StaffInfo {
  final String staffId;
  final String name;
  final String role;
  final String department;

  const StaffInfo({
    required this.staffId,
    required this.name,
    required this.role,
    required this.department,
  });

  factory StaffInfo.fromJson(Map<String, dynamic> json) => StaffInfo(
        staffId: json['staff_id'] as String,
        name: json['name'] as String,
        role: json['role'] as String,
        department: json['department'] as String,
      );

  String get roleDisplay => role.replaceAll('_', ' ').toUpperCase();
}

class ProtocolInfo {
  final String name;
  final String code;
  final List<String> steps;

  const ProtocolInfo({
    required this.name,
    required this.code,
    required this.steps,
  });

  factory ProtocolInfo.fromJson(Map<String, dynamic> json) => ProtocolInfo(
        name: json['name'] as String,
        code: json['code'] as String,
        steps: (json['steps'] as List<dynamic>).cast<String>(),
      );
}

enum UrgencyLevel { critical, high, medium, unknown }

extension UrgencyLevelExt on UrgencyLevel {
  static UrgencyLevel fromString(String s) {
    return switch (s.toLowerCase()) {
      'critical' => UrgencyLevel.critical,
      'high' => UrgencyLevel.high,
      'medium' => UrgencyLevel.medium,
      _ => UrgencyLevel.unknown,
    };
  }

  String get label => name.toUpperCase();
}

class CrisisResponse {
  final String eventId;
  final String status;
  final String crisisType;
  final String location;
  final UrgencyLevel urgency;
  final String summary;
  final ProtocolInfo protocol;
  final List<StaffInfo> staffDispatched;
  final bool fcmSent;
  final String dispatchMode;
  final int responseMs;

  const CrisisResponse({
    required this.eventId,
    required this.status,
    required this.crisisType,
    required this.location,
    required this.urgency,
    required this.summary,
    required this.protocol,
    required this.staffDispatched,
    required this.fcmSent,
    required this.dispatchMode,
    required this.responseMs,
  });

  factory CrisisResponse.fromJson(Map<String, dynamic> json) => CrisisResponse(
        eventId: json['event_id'] as String,
        status: json['status'] as String,
        crisisType: json['crisis_type'] as String,
        location: json['location'] as String,
        urgency: UrgencyLevelExt.fromString(json['urgency'] as String),
        summary: json['summary'] as String,
        protocol: ProtocolInfo.fromJson(json['protocol'] as Map<String, dynamic>),
        staffDispatched: (json['staff_dispatched'] as List<dynamic>)
            .map((e) => StaffInfo.fromJson(e as Map<String, dynamic>))
            .toList(),
        fcmSent: json['fcm_sent'] as bool,
        dispatchMode: json['dispatch_mode'] as String,
        responseMs: json['response_ms'] as int,
      );
}

enum PipelineStep {
  idle,
  recording,
  transcribing,
  thinking,
  findingProtocol,
  findingStaff,
  dispatching,
  done,
  error,
}

extension PipelineStepExt on PipelineStep {
  String get label => switch (this) {
        PipelineStep.idle => 'Ready',
        PipelineStep.recording => 'Recording...',
        PipelineStep.transcribing => 'Transcribing voice...',
        PipelineStep.thinking => 'Gemini analyzing crisis...',
        PipelineStep.findingProtocol => 'Fetching protocol...',
        PipelineStep.findingStaff => 'Locating available staff...',
        PipelineStep.dispatching => 'Dispatching alerts...',
        PipelineStep.done => 'Dispatched ✓',
        PipelineStep.error => 'Error',
      };

  int get index => PipelineStep.values.indexOf(this);
}
