import 'package:flutter/material.dart';
import 'package:farmmatrix/config/app_config.dart';
import 'dart:math' as math;

class PrimaryButton extends StatelessWidget {
  final String text;
  final VoidCallback onPressed;
  final bool showArrow;
  final double width;

  const PrimaryButton({
    super.key,
    required this.text,
    required this.onPressed,
    this.showArrow = true,
    this.width = double.infinity,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      child: ElevatedButton(
        onPressed: onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: AppConfig.primaryColor, // Now uses 0xFF1B413C
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(30),
          ),
          elevation: 5,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              text, // Ensure this is a translated string from the caller
              style: const TextStyle(
                fontFamily: AppConfig.fontFamily, // Now PlusJakartaSans
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            if (showArrow) ...[
              const SizedBox(width: 8),
              const Icon(Icons.arrow_forward),
            ],
          ],
        ),
      ),
    );
  }
}

class FarmMatrixLogo extends StatelessWidget {
  final double size;

  const FarmMatrixLogo({super.key, this.size = 100});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: Colors.white,
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 10,
            spreadRadius: 1,
          ),
        ],
      ),
      child: Center(
        child: Stack(
          alignment: Alignment.center,
          children: [
            // Sun
            Container(
              width: size * 0.4,
              height: size * 0.4,
              decoration: const BoxDecoration(
                color: Colors.orange,
                shape: BoxShape.circle,
              ),
            ),

            // Fields
            Positioned(
              bottom: size * 0.25,
              child: Container(
                width: size * 0.8,
                height: size * 0.25,
                decoration: BoxDecoration(
                  color: AppConfig.primaryColor, // Now uses 0xFF1B413C
                  borderRadius: BorderRadius.circular(size * 0.1),
                ),
              ),
            ),

            // Text
            Positioned(
              bottom: size * 0.05,
              child: Text(
                'FARMMATRIX', // Consider translating this if needed
                style: const TextStyle(
                  fontFamily: AppConfig.fontFamily, // Now PlusJakartaSans
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: AppConfig.secondaryColor,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class LanguageOption extends StatelessWidget {
  final String language;
  final String languageCode;
  final bool isSelected;
  final VoidCallback onTap;
  final Widget? flagWidget;
  final bool enabled;

  const LanguageOption({
    super.key,
    required this.language,
    required this.languageCode,
    required this.isSelected,
    required this.onTap,
    this.flagWidget,
    this.enabled = true,
  });

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: enabled ? 1.0 : 0.5,
      child: GestureDetector(
        onTap: enabled ? onTap : null,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            border: Border.all(
              color: isSelected ? AppConfig.primaryColor : Colors.grey.shade300, // Now uses 0xFF1B413C
              width: isSelected ? 2 : 1,
            ),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Row(
            children: [
              // Flag
              if (flagWidget != null) ...[
                flagWidget!,
                const SizedBox(width: 16),
              ],

              // Language Name
              Text(
                language, // Consider translating this if needed
                style: TextStyle(
                  fontFamily: AppConfig.fontFamily, // Now PlusJakartaSans
                  fontSize: 16,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                ),
              ),

              const Spacer(),

              // Radio Button
              Container(
                width: 20,
                height: 20,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: isSelected ? AppConfig.primaryColor : Colors.grey, // Now uses 0xFF1B413C
                    width: 2,
                  ),
                ),
                child: isSelected
                    ? Center(
                        child: Container(
                          width: 10,
                          height: 10,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: AppConfig.primaryColor, // Now uses 0xFF1B413C
                          ),
                        ),
                      )
                    : null,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class CountryFlag extends StatelessWidget {
  final String countryCode;

  const CountryFlag({super.key, required this.countryCode});

  @override
  Widget build(BuildContext context) {
    // Use simple colored containers with text instead of custom painters
    if (countryCode == 'uk') {
      return Container(
        width: 30,
        height: 20,
        decoration: BoxDecoration(
          color: Colors.blue[900],
          border: Border.all(color: Colors.grey.shade300),
          borderRadius: BorderRadius.circular(4),
        ),
        child: const Center(
          child: Text(
            'UK',
            style: TextStyle(
              color: Colors.white,
              fontSize: 10,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
      );
    } else if (countryCode == 'in') {
      return Container(
        width: 30,
        height: 20,
        decoration: BoxDecoration(
          color: Colors.orange,
          border: Border.all(color: Colors.grey.shade300),
          borderRadius: BorderRadius.circular(4),
        ),
        child: const Center(
          child: Text(
            'IN',
            style: TextStyle(
              color: Colors.white,
              fontSize: 10,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
      );
    }

    // Default placeholder
    return Container(
      width: 30,
      height: 20,
      color: Colors.grey,
      child: Center(
        child: Text(
          countryCode.toUpperCase(),
          style: const TextStyle(
            color: Colors.white,
            fontSize: 10,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }
}

double cos(double radians) {
  return math.cos(radians);
}

double sin(double radians) {
  return math.sin(radians);
}