// import 'package:flutter/material.dart';
// import 'package:shared_preferences/shared_preferences.dart';

// class LanguageProvider extends ChangeNotifier {
//   Locale _locale = const Locale('en', 'US');
//   final String _prefsKey = 'language_code';

//   Locale get locale => _locale;

//   LanguageProvider() {
//     _loadSavedLanguage();
//   }

//   Future<void> _loadSavedLanguage() async {
//     final prefs = await SharedPreferences.getInstance();
//     final savedLanguage = prefs.getString(_prefsKey);
    
//     if (savedLanguage != null) {
//       if (savedLanguage == 'hi') {
//         _locale = const Locale('hi', 'IN');
//       } else {
//         _locale = const Locale('en', 'US');
//       }
//       notifyListeners();
//     }
//   }

//   Future<void> setLanguage(String languageCode) async {
//     if (languageCode == 'hi') {
//       _locale = const Locale('hi', 'IN');
//     } else {
//       _locale = const Locale('en', 'US');
//     }
    
//     final prefs = await SharedPreferences.getInstance();
//     await prefs.setString(_prefsKey, languageCode);
    
//     notifyListeners();
//   }
// }

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class LanguageProvider extends ChangeNotifier {
  Locale _locale = const Locale('en', 'US');
  final String _prefsKey = 'language_code';

  Locale get locale => _locale;

  LanguageProvider() {
    _loadSavedLanguage();
  }

  Future<void> _loadSavedLanguage() async {
    final prefs = await SharedPreferences.getInstance();
    final savedLanguage = prefs.getString(_prefsKey);

    if (savedLanguage != null) {
      if (savedLanguage == 'hi') {
        _locale = const Locale('hi', 'IN');
      } else if (savedLanguage == 'mr') {
        _locale = const Locale('mr', 'IN');
      } else {
        _locale = const Locale('en', 'US');
      }
      notifyListeners();
    }
  }

  Future<void> setLanguage(String languageCode) async {
    if (languageCode == 'hi') {
      _locale = const Locale('hi', 'IN');
    } else if (languageCode == 'mr') {
      _locale = const Locale('mr', 'IN');
    } else {
      _locale = const Locale('en', 'US');
    }

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefsKey, languageCode);

    notifyListeners();
  }
}