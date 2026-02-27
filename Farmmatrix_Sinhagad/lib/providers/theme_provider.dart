import 'package:flutter/material.dart';
import 'package:farmmatrix/config/app_config.dart';

class ThemeProvider extends ChangeNotifier {
  ThemeMode _themeMode = ThemeMode.light;

  ThemeMode get themeMode => _themeMode;

  bool get isDarkMode => _themeMode == ThemeMode.dark;

  void toggleTheme() {
    _themeMode = _themeMode == ThemeMode.light ? ThemeMode.dark : ThemeMode.light;
    notifyListeners();
  }

  ThemeData get lightTheme {
    return ThemeData(
      primaryColor: AppConfig.primaryColor,
      colorScheme: ColorScheme.light(
        primary: AppConfig.primaryColor,
        secondary: AppConfig.secondaryColor,
      ),
      scaffoldBackgroundColor: Colors.white,
      fontFamily: AppConfig.fontFamily,
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: AppConfig.primaryButtonStyle,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppConfig.primaryColor,
        foregroundColor: Colors.white,
      ),
    );
  }

  ThemeData get darkTheme {
    return ThemeData(
      primaryColor: AppConfig.primaryColor,
      colorScheme: ColorScheme.dark(
        primary: AppConfig.primaryColor,
        secondary: AppConfig.accentColor,
      ),
      scaffoldBackgroundColor: Colors.grey[900],
      fontFamily: AppConfig.fontFamily,
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: AppConfig.primaryButtonStyle,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppConfig.secondaryColor,
        foregroundColor: Colors.white,
      ),
    );
  }
}
