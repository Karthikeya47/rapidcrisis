/// theme.dart — Design system for Rapid Crisis Response app
library;
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

// ── Color Palette ─────────────────────────────────────────────
class AppColors {
  // Background
  static const bg = Color(0xFF08090C);
  static const surface = Color(0xFF111318);
  static const surfaceElevated = Color(0xFF181C24);
  static const border = Color(0xFF1F2430);

  // Critical / Urgency
  static const critical = Color(0xFFFF3B5C);
  static const criticalDim = Color(0x33FF3B5C);
  static const high = Color(0xFFFF8C00);
  static const highDim = Color(0x33FF8C00);
  static const medium = Color(0xFFFFD600);
  static const mediumDim = Color(0x33FFD600);

  // Accent
  static const accent = Color(0xFF00D4FF);
  static const accentDim = Color(0x2200D4FF);
  static const accentGreen = Color(0xFF00FF9F);
  static const accentGreenDim = Color(0x2200FF9F);

  // Text
  static const textPrimary = Color(0xFFEEF0F6);
  static const textSecondary = Color(0xFF6B7280);
  static const textMuted = Color(0xFF374151);

  // Pipeline step states
  static const stepActive = accent;
  static const stepDone = accentGreen;
  static const stepPending = Color(0xFF2A3040);
}

// ── Typography ────────────────────────────────────────────────
class AppTextStyles {
  static TextStyle get displayLarge => GoogleFonts.outfit(
        fontSize: 32,
        fontWeight: FontWeight.w800,
        color: AppColors.textPrimary,
        letterSpacing: -0.5,
      );

  static TextStyle get heading => GoogleFonts.outfit(
        fontSize: 20,
        fontWeight: FontWeight.w700,
        color: AppColors.textPrimary,
      );

  static TextStyle get subheading => GoogleFonts.outfit(
        fontSize: 14,
        fontWeight: FontWeight.w500,
        color: AppColors.textSecondary,
        letterSpacing: 0.5,
      );

  static TextStyle get body => GoogleFonts.inter(
        fontSize: 14,
        fontWeight: FontWeight.w400,
        color: AppColors.textPrimary,
      );

  static TextStyle get caption => GoogleFonts.inter(
        fontSize: 12,
        fontWeight: FontWeight.w400,
        color: AppColors.textSecondary,
      );

  static TextStyle get mono => GoogleFonts.jetBrainsMono(
        fontSize: 12,
        color: AppColors.textSecondary,
      );

  static TextStyle get label => GoogleFonts.outfit(
        fontSize: 11,
        fontWeight: FontWeight.w600,
        color: AppColors.textSecondary,
        letterSpacing: 1.2,
      );
}

// ── Theme ─────────────────────────────────────────────────────
ThemeData buildAppTheme() {
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: AppColors.bg,
    colorScheme: const ColorScheme.dark(
      primary: AppColors.accent,
      secondary: AppColors.accentGreen,
      error: AppColors.critical,
      surface: AppColors.surface,
    ),
    textTheme: GoogleFonts.interTextTheme(ThemeData.dark().textTheme),
    appBarTheme: AppBarTheme(
      backgroundColor: AppColors.bg,
      elevation: 0,
      centerTitle: false,
      titleTextStyle: AppTextStyles.heading,
      iconTheme: const IconThemeData(color: AppColors.textPrimary),
    ),
    cardTheme: CardThemeData(
      color: AppColors.surfaceElevated,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AppColors.border, width: 1),
      ),
      elevation: 0,
      margin: EdgeInsets.zero,
    ),
    dividerTheme: const DividerThemeData(
      color: AppColors.border,
      thickness: 1,
    ),
  );
}
