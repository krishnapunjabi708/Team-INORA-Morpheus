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
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Logo
              Center(
                child: Image.asset('assets/images/logo.png', width: 200, height: 140),
              ),
              const SizedBox(height: 32),

              // Language Selection Header
              Container(
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
                decoration: BoxDecoration(
                  color: AppConfig.accentColor,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.language, color: Colors.black87),
                    const SizedBox(width: 8),
                    Text(
                      AppLocalizations.of(context)!.selectLanguage,
                      style: const TextStyle(
                        fontFamily: AppConfig.fontFamily,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Colors.black87,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // Language Options
              LanguageOption(
                language: "English",
                languageCode: 'en',
                isSelected: _selectedLanguage == 'en',
                onTap: () {
                  setState(() {
                    _selectedLanguage = 'en';
                  });
                },
                flagWidget: const CountryFlag(countryCode: 'uk'),
              ),
              const SizedBox(height: 12),
              LanguageOption(
                language: "हिंदी",
                languageCode: 'hi',
                isSelected: _selectedLanguage == 'hi',
                onTap: () {
                  setState(() {
                    _selectedLanguage = 'hi';
                  });
                },
                flagWidget: const CountryFlag(countryCode: 'in'),
              ),
              const SizedBox(height: 12),
              LanguageOption(
                language: "मराठी",
                languageCode: 'mr',
                isSelected: _selectedLanguage == 'mr',
                onTap: () {
                  setState(() {
                    _selectedLanguage = 'mr';
                  });
                },
                flagWidget: const CountryFlag(countryCode: 'in'),
              ),

              const Spacer(),

              // Next Button
              PrimaryButton(
                text: AppLocalizations.of(context)!.next,
                onPressed: () {
                  Provider.of<LanguageProvider>(context, listen: false)
                      .setLanguage(_selectedLanguage);
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => const LoginScreen(),
                    ),
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}