

import 'package:flutter/material.dart';
import 'package:farmmatrix/config/app_config.dart';
import 'package:farmmatrix/screens/language_selection/language_selection_screen.dart';
import 'package:farmmatrix/l10n/app_localizations.dart';
import 'package:farmmatrix/widgets/common_widgets.dart';

class WelcomeScreen extends StatelessWidget {
  const WelcomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          // Background Image with Opacity
          Opacity(
            opacity: 0.65,
            child: Container(
              width: double.infinity,
              height: double.infinity,
              color: AppConfig.primaryColor.withOpacity(0.3),
              child: Image.asset(
                'assets/images/bg_Image.png',
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) {
                  return Container(
                    color: AppConfig.primaryColor.withOpacity(0.3),
                    child: Center(
                      child: Icon(
                        Icons.landscape,
                        size: 100,
                        color: Colors.white.withOpacity(0.5),
                      ),
                    ),
                  );
                },
              ),
            ),
          ),

          // Content
          SafeArea(
            child: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  // Logo and Tagline
                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        // Logo
                        Image.asset('assets/images/logo.png', width: 200, height: 140),
                        // Tagline
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 32),
                          child: Text(
                            AppLocalizations.of(context)!.welcomeMessage, // Use generated key
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                              fontFamily: AppConfig.fontFamily,
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: Color.fromARGB(255, 0, 0, 0),
                              shadows: [
                                Shadow(
                                  offset: Offset(1, 1),
                                  blurRadius: 3,
                                  color: Colors.black54,
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Get Started Button
                  Padding(
                    padding: const EdgeInsets.only(bottom: 40, left: 32, right: 32),
                    child: PrimaryButton(
                      text: AppLocalizations.of(context)!.getStarted, // Use generated key
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => const LanguageSelectionScreen(),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}