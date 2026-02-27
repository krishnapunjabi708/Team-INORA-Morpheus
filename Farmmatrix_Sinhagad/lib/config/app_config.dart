// import 'package:flutter/material.dart';

// class AppConfig {
//   // App Colors
//   static const Color primaryColor = Color(0xFF5DA849);
//   static const Color secondaryColor = Color(0xFF13251F);
//   static const Color accentColor = Color(0xFFFFD17B);
//   static const Color textColor = Color(0xFF333333);
//   static const Color backgroundColor = Colors.white;
  
//   // Gradient for Login/Signup screens
//   static const LinearGradient authGradient = LinearGradient(
//     begin: Alignment.topLeft,
//     end: Alignment.bottomRight,
//     colors: [
//       Color(0xFF13251F),
//       Color(0xFF5DA849),
//     ],
//   );
  
//   // Text Styles
//   static const String fontFamily = 'PTSansNarrow';
  
//   static TextStyle headingStyle = const TextStyle(
//     fontFamily: fontFamily,
//     fontSize: 24,
//     fontWeight: FontWeight.bold,
//     color: textColor,
//   );
  
//   static TextStyle subheadingStyle = const TextStyle(
//     fontFamily: fontFamily,
//     fontSize: 18,
//     fontWeight: FontWeight.w500,
//     color: textColor,
//   );
  
//   static TextStyle bodyStyle = const TextStyle(
//     fontFamily: fontFamily,
//     fontSize: 16,
//     color: textColor,
//   );
  
//   static TextStyle buttonTextStyle = const TextStyle(
//     fontFamily: fontFamily,
//     fontSize: 16,
//     fontWeight: FontWeight.bold,
//     color: Colors.white,
//   );
  
//   // Button Style
//   static final ButtonStyle primaryButtonStyle = ElevatedButton.styleFrom(
//     backgroundColor: primaryColor,
//     foregroundColor: Colors.white,
//     shape: RoundedRectangleBorder(
//       borderRadius: BorderRadius.circular(30),
//     ),
//     elevation: 3,
//     padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 24),
//   );
  
//   // Input Field Style
//   static InputDecoration inputDecoration(String hintText) {
//     return InputDecoration(
//       hintText: hintText,
//       filled: true,
//       fillColor: accentColor,
//       border: OutlineInputBorder(
//         borderRadius: BorderRadius.circular(10),
//         borderSide: BorderSide.none,
//       ),
//       contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
//       hintStyle: TextStyle(
//         fontFamily: fontFamily,
//         color: textColor.withOpacity(0.7),
//       ),
//     );
//   }
// }


import 'package:flutter/material.dart';

class AppConfig {
  // App Colors
  static const Color primaryColor = Color(0xFF1B413C); // Changed from 0xFF5DA849
  static const Color secondaryColor = Color(0xFF13251F);
  static const Color accentColor = Color(0xFFDB9F75); // Changed from 0xFFFFD17B
  static const Color textColor = Color(0xFF333333);
  static const Color backgroundColor = Colors.white;
  
  // Gradient for Login/Signup screens
  static const LinearGradient authGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0xFF13251F),
      Color(0xFF1B413C), // Updated to match new primary color
    ],
  );
  
  // Text Styles
  static const String fontFamily = 'PlusJakartaSans'; // Changed from 'PTSansNarrow'
  
  static TextStyle headingStyle = const TextStyle(
    fontFamily: fontFamily,
    fontSize: 24,
    fontWeight: FontWeight.bold,
    color: textColor,
  );
  
  static TextStyle subheadingStyle = const TextStyle(
    fontFamily: fontFamily,
    fontSize: 18,
    fontWeight: FontWeight.w500,
    color: textColor,
  );
  
  static TextStyle bodyStyle = const TextStyle(
    fontFamily: fontFamily,
    fontSize: 16,
    color: textColor,
  );
  
  static TextStyle buttonTextStyle = const TextStyle(
    fontFamily: fontFamily,
    fontSize: 16,
    fontWeight: FontWeight.bold,
    color: Colors.white,
  );
  
  // Button Style
  static final ButtonStyle primaryButtonStyle = ElevatedButton.styleFrom(
    backgroundColor: primaryColor,
    foregroundColor: Colors.white,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(30),
    ),
    elevation: 3,
    padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 24),
  );
  
  // Input Field Style
  static InputDecoration inputDecoration(String hintText) {
    return InputDecoration(
      hintText: hintText,
      filled: true,
      fillColor: accentColor,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide.none,
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      hintStyle: TextStyle(
        fontFamily: fontFamily,
        color: textColor.withOpacity(0.7),
      ),
    );
  }
}