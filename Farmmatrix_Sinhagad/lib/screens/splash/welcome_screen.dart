

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:farmmatrix/screens/language_selection/language_selection_screen.dart';
import 'package:farmmatrix/screens/home/home_screen.dart';
import 'package:farmmatrix/widgets/common_widgets.dart';
import 'package:farmmatrix/l10n/app_localizations.dart';

class WelcomeScreen extends StatefulWidget {
  const WelcomeScreen({super.key});

  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;

  @override
  void initState() {
    super.initState();
    _checkLoginStatus();
  }

  Future<void> _checkLoginStatus() async {
    final prefs = await SharedPreferences.getInstance();
    final userId = prefs.getString("userId");

    if (userId != null && mounted) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const HomeScreen()),
      );
    }
  }

  void _nextPage() {
    if (_currentPage == 1) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => const LanguageSelectionScreen(),
        ),
      );
    } else {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 400),
        curve: Curves.easeInOut,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;

    final List<Map<String, String>> pages = [
      {
        "image": "assets/images/onboarding1.jpeg",
        "description": loc.onboardingDesc1,
      },
      {
        "image": "assets/images/onboarding2.jpeg",
        "description": loc.onboardingDesc2,
      },
    ];

    return Scaffold(
      extendBodyBehindAppBar: true,
      backgroundColor: Colors.white,
      body: MediaQuery.removePadding(
        context: context,
        removeTop: true,
        child: PageView.builder(
          controller: _pageController,
          itemCount: pages.length,
          onPageChanged: (index) {
            setState(() => _currentPage = index);
          },
          itemBuilder: (context, index) {
            return Column(
              children: [

                /// -------- TOP IMAGE SECTION --------
                Container(
                  height: MediaQuery.of(context).size.height * 0.60,
                  width: double.infinity,
                  child: Image.asset(
                    pages[index]["image"]!,
                    fit: BoxFit.contain,
                  ),
                ),

                /// -------- WHITE CONTENT SECTION --------
                Expanded(
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 30, vertical: 30),
                    decoration: const BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.vertical(
                        top: Radius.circular(30),
                      ),
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [

                        /// Description
                        Text(
                          pages[index]["description"]!,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w500,
                          ),
                        ),

                        const SizedBox(height: 25),

                        /// Dots Indicator
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: List.generate(
                            pages.length,
                            (dotIndex) => AnimatedContainer(
                              duration: const Duration(milliseconds: 300),
                              margin: const EdgeInsets.symmetric(horizontal: 4),
                              height: 8,
                              width: _currentPage == dotIndex ? 20 : 8,
                              decoration: BoxDecoration(
                                color: _currentPage == dotIndex
                                    ? const Color(0xFFFFC107)
                                    : Colors.grey.shade300,
                                borderRadius: BorderRadius.circular(20),
                              ),
                            ),
                          ),
                        ),

                        const SizedBox(height: 30),

                        /// Primary Button
                        PrimaryButton(
                          text: _currentPage == pages.length - 1
                              ? loc.getStarted
                              : loc.next,
                          width: 200,
                          showArrow: false,
                          onPressed: _nextPage,
                        ),

                        const SizedBox(height: 10),

                        /// Skip Option
                        if (_currentPage != pages.length - 1)
                          TextButton(
                            onPressed: () {
                              Navigator.pushReplacement(
                                context,
                                MaterialPageRoute(
                                  builder: (_) =>
                                      const LanguageSelectionScreen(),
                                ),
                              );
                            },
                            child: Text(
                              loc.skip,
                              style: const TextStyle(
                                fontSize: 13,
                                color: Colors.grey,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}