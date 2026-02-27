import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:farmmatrix/providers/language_provider.dart';
import 'package:farmmatrix/l10n/app_localizations.dart'; // assuming SimpleLanguageTile is here

class ChangeLanguageScreen extends StatefulWidget {
  const ChangeLanguageScreen({super.key});

  @override
  State<ChangeLanguageScreen> createState() => _ChangeLanguageScreenState();
}

class _ChangeLanguageScreenState extends State<ChangeLanguageScreen> {
  late String _selectedLanguage;

  @override
  void initState() {
    super.initState();
    // Start with current language from provider
    final currentLocale = Provider.of<LanguageProvider>(context, listen: false).locale.languageCode;
    _selectedLanguage = currentLocale;
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;

    return Scaffold(
      backgroundColor: const Color(0xFFF2F2F2),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1B413C),
        foregroundColor: Colors.white,
        title: Text(
          loc.changeLanguage,        
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    const SizedBox(height: 20),

                    // Optional: small logo or icon at top
                    Image.asset(
                      'assets/images/logo.png',
                      width: 120,
                    ),

                    const SizedBox(height: 32),

                    // Title
                    Text(
                      loc.selectLanguage,
                      style: const TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w600,
                        color: Colors.black87,
                      ),
                    ),

                    const SizedBox(height: 32),

                    // Language list
                    Column(
                      children: [
                        _buildLanguageTile(loc.english, 'en'),
                        const SizedBox(height: 14),
                        _buildLanguageTile(loc.hindi, 'hi'),
                        const SizedBox(height: 14),
                        _buildLanguageTile(loc.marathi, 'mr'),
                      ],
                    ),

                    const SizedBox(height: 40),
                  ],
                ),
              ),
            ),

            // Save Button (bottom fixed)
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
              child: ElevatedButton(
                onPressed: () {
                  Provider.of<LanguageProvider>(context, listen: false)
                      .setLanguage(_selectedLanguage);
                  Navigator.pop(context); // Go back to Profile
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF1B413C),
                  foregroundColor: Colors.white,
                  minimumSize: const Size(double.infinity, 54),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: Text(
                  loc.save,           // ← Add this key too
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLanguageTile(String title, String code) {
    final bool isSelected = _selectedLanguage == code;

    return GestureDetector(
      onTap: () {
        setState(() => _selectedLanguage = code);
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFF1B413C).withOpacity(0.1) : Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? const Color(0xFF1B413C) : Colors.grey.shade300,
            width: 1.5,
          ),
        ),
        child: Row(
          children: [
            Text(
              title,
              style: TextStyle(
                fontSize: 17,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                color: isSelected ? const Color(0xFF1B413C) : Colors.black87,
              ),
            ),
            const Spacer(),
            if (isSelected)
              const Icon(
                Icons.check_circle,
                color: Color(0xFF1B413C),
                size: 26,
              ),
          ],
        ),
      ),
    );
  }
}