import 'package:flutter/material.dart';
import 'package:farmmatrix/config/app_config.dart';
import 'package:farmmatrix/providers/language_provider.dart';
import 'package:farmmatrix/screens/auth/login_screen.dart';
import 'package:farmmatrix/l10n/app_localizations.dart';
import 'package:farmmatrix/widgets/common_widgets.dart';
import 'package:provider/provider.dart';

class LanguageSelectionScreen extends StatefulWidget {
  const LanguageSelectionScreen({super.key});

  @override
  State<LanguageSelectionScreen> createState() => _LanguageSelectionScreenState();
}

class _LanguageSelectionScreenState extends State<LanguageSelectionScreen> {
  String _selectedLanguage = 'en';

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    const SizedBox(height: 30),

                    // Logo
                    Image.asset(
                      'assets/images/logo.png',
                      width: 170,
                    ),

                    const SizedBox(height: 40),

                    // Title
                    Text(
                      loc.selectLanguage,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                        color: Colors.black87,
                      ),
                    ),

                    const SizedBox(height: 32),

                    // Scrollable list of languages
                    Column(
                      children: [
                        // English
                        SimpleLanguageTile(
                          title: loc.english,
                          isSelected: _selectedLanguage == 'en',
                          onTap: () => setState(() => _selectedLanguage = 'en'),
                        ),
                        const SizedBox(height: 14),

                        // Hindi
                        SimpleLanguageTile(
                          title: loc.hindi,
                          isSelected: _selectedLanguage == 'hi',
                          onTap: () => setState(() => _selectedLanguage = 'hi'),
                        ),
                        const SizedBox(height: 14),

                        // Marathi
                        SimpleLanguageTile(
                          title: loc.marathi,
                          isSelected: _selectedLanguage == 'mr',
                          onTap: () => setState(() => _selectedLanguage = 'mr'),
                        ),
                        const SizedBox(height: 14),
                      ],
                    ),

                    const SizedBox(height: 40),
                  ],
                ),
              ),
            ),

            // Next Button – fixed at bottom
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
              child: PrimaryButton(
                text: loc.next,
                width: double.infinity,
                showArrow: false,
                onPressed: () {
                  Provider.of<LanguageProvider>(context, listen: false)
                      .setLanguage(_selectedLanguage);

                  Navigator.pushReplacement(
                    context,
                    MaterialPageRoute(builder: (_) => const LoginScreen()),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}