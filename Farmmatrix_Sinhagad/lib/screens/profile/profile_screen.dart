import 'package:flutter/material.dart';
import 'package:farmmatrix/config/app_config.dart';
import 'package:farmmatrix/models/user_model.dart';
import 'package:farmmatrix/services/user_service.dart';
import 'package:farmmatrix/services/auth_services.dart';
import 'package:farmmatrix/screens/home/home_screen.dart';
import 'package:farmmatrix/screens/dashboard/dashboard.dart';
import 'package:farmmatrix/screens/profile/government_schemes_screen.dart';
import 'package:farmmatrix/screens/field_add_selection/select_field_dropdown.dart';
import 'package:farmmatrix/screens/auth/login_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:farmmatrix/models/field_info_model.dart';
import 'dart:convert';
import 'package:farmmatrix/l10n/app_localizations.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  _ProfileScreenState createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  UserModel? _user;
  final UserService _userService = UserService();
  int _selectedIndex = 2;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchUserData();
  }

  Future<void> _fetchUserData() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final userId = prefs.getString('userId');

      if (userId == null) {
        print(AppLocalizations.of(context)!.noUserIdFound);
        setState(() {
          _user = null;
          _isLoading = false;
        });
        return;
      }

      final userData = await _userService.getUserData(userId);
      setState(() {
        _user = userData;
        _isLoading = false;
      });
    } catch (e) {
      print(AppLocalizations.of(context)!.errorFetchingUserData(e.toString()));
      setState(() {
        _user = null;
        _isLoading = false;
      });
    }
  }

  Future<void> _handleLogout() async {
    setState(() {
      _isLoading = true;
    });

    try {
      final prefs = await SharedPreferences.getInstance();
      final userId = prefs.getString('userId');

      if (userId != null) {
        await AuthServices.deleteUser(userId);
      }

      await prefs.remove('userId');
      await prefs.remove('selectedField');

      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (context) => const LoginScreen()),
        );
      }
    } catch (e) {
      print(AppLocalizations.of(context)!.errorLoggingOut(e.toString()));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              AppLocalizations.of(context)!.errorLoggingOut(e.toString()),
            ),
          ),
        );
      }
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<FieldInfoModel?> _loadSelectedField() async {
    final prefs = await SharedPreferences.getInstance();
    final fieldJson = prefs.getString('selectedField');
    if (fieldJson != null) {
      try {
        final fieldMap = jsonDecode(fieldJson) as Map<String, dynamic>;
        return FieldInfoModel.fromMap(fieldMap);
      } catch (e) {
        print(AppLocalizations.of(context)!.errorDecodingField(e.toString()));
        return null;
      }
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF1F1F1),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        automaticallyImplyLeading: false,
        leadingWidth: 68,
        leading: Row(
          children: [
            const SizedBox(width: 18),
            Image.asset('assets/images/logo.png', width: 47, height: 47),
          ],
        ),
        title: Text(
          AppLocalizations.of(context)!.farmMatrix,
          style: TextStyle(
            fontFamily: AppConfig.fontFamily,
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: AppConfig.secondaryColor,
          ),
        ),
      ),
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            alignment: Alignment.centerLeft,
            child: Text(
              AppLocalizations.of(context)!.account,
              style: TextStyle(
                fontFamily: AppConfig.fontFamily,
                fontSize: 24,
                fontWeight: FontWeight.bold,
                foreground:
                    Paint()
                      ..shader = LinearGradient(
                        colors: [
                          AppConfig.primaryColor,
                          AppConfig.primaryColor,
                        ],
                      ).createShader(const Rect.fromLTWH(0, 0, 200, 70)),
              ),
            ),
          ),
          Container(
            margin: const EdgeInsets.all(16),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              border: Border.all(color: Colors.black),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Row(
                  children: [
                    const Icon(Icons.person, size: 40),
                    const SizedBox(width: 8),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _isLoading
                            ? const CircularProgressIndicator()
                            : Text(
                              AppLocalizations.of(context)!.helloUser(
                                _user?.fullName ??
                                    AppLocalizations.of(context)!.defaultUser,
                              ),
                              style: TextStyle(
                                fontFamily: AppConfig.fontFamily,
                                fontWeight: FontWeight.bold,
                                fontSize: 18,
                                foreground:
                                    Paint()
                                      ..shader = LinearGradient(
                                        colors: [
                                          AppConfig.primaryColor,
                                          AppConfig.primaryColor.withOpacity(
                                            0.8,
                                          ),
                                        ],
                                      ).createShader(
                                        const Rect.fromLTWH(0, 0, 200, 70),
                                      ),
                              ),
                            ),
                        const SizedBox(height: 4),
                        _isLoading
                            ? const SizedBox(
                              width: 100,
                              height: 16,
                              child: LinearProgressIndicator(),
                            )
                            : Text(
                              _user?.phoneNumber ??
                                  AppLocalizations.of(context)!.noPhone,
                              style: TextStyle(
                                fontFamily: AppConfig.fontFamily,
                                color:
                                    AppConfig
                                        .primaryColor, // Changed to primary color
                                fontSize: 16,
                              ),
                            ),
                      ],
                    ),
                  ],
                ),
                const Padding(
                  padding: EdgeInsets.only(top: 4),
                  child: Icon(Icons.edit),
                ),
              ],
            ),
          ),
          GestureDetector(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder:
                      (context) => SelectFieldDropdown(
                        onFieldSelected: (FieldInfoModel? field) {
                          print(
                            AppLocalizations.of(
                              context,
                            )!.selectedField(field?.fieldName ?? 'None'),
                          );
                        },
                      ),
                ),
              );
            },
            child: _buildRoundedRectangle(
              AppLocalizations.of(context)!.myFields,
              Icons.landscape,
            ),
          ),
          GestureDetector(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const GovernmentSchemesScreen(),
                ),
              );
            },
            child: _buildRoundedRectangle(
              AppLocalizations.of(context)!.governmentSchemes,
              Icons.business,
            ),
          ),
          GestureDetector(
            onTap: _handleLogout,
            child: _buildRoundedRectangle(
              AppLocalizations.of(context)!.logout,
              Icons.logout,
            ),
          ),
          if (_isLoading == false && _user == null)
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: ElevatedButton(
                onPressed: () {
                  setState(() {
                    _isLoading = true;
                  });
                  _fetchUserData();
                },
                child: Text(
                  AppLocalizations.of(context)!.refreshUserData,
                  style: TextStyle(
                    fontFamily: AppConfig.fontFamily,
                    color: AppConfig.primaryColor, // Changed to primary color
                  ),
                ),
              ),
            ),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        backgroundColor: Colors.white,
        type: BottomNavigationBarType.fixed,
        currentIndex: _selectedIndex,
        items: [
          BottomNavigationBarItem(
            icon: const Icon(Icons.home),
            label: AppLocalizations.of(context)!.home,
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.dashboard),
            label: AppLocalizations.of(context)!.dashboard,
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.person),
            label: AppLocalizations.of(context)!.profile,
          ),
        ],
        onTap: (index) async {
          setState(() {
            _selectedIndex = index;
          });

          if (index == 0) {
            Navigator.pushReplacement(
              context,
              MaterialPageRoute(builder: (context) => const HomeScreen()),
            );
          } else if (index == 1) {
            final selectedField = await _loadSelectedField();
            Navigator.push(
              context,
              MaterialPageRoute(
                builder:
                    (context) => DashboardScreen(selectedField: selectedField),
              ),
            );
          }
        },
        showSelectedLabels: true,
        showUnselectedLabels: true,
        selectedItemColor: const Color(0xFF5FA748),
        unselectedItemColor: const Color(0xFF757575),
        elevation: 8,
        iconSize: 24,
        selectedLabelStyle: TextStyle(fontFamily: AppConfig.fontFamily),
        unselectedLabelStyle: TextStyle(fontFamily: AppConfig.fontFamily),
      ),
    );
  }

  Widget _buildRoundedRectangle(String title, IconData icon) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppConfig.accentColor, // Changed to accent color
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  icon,
                  color: AppConfig.primaryColor, // Changed to primary color
                ),
              ),
              const SizedBox(width: 8),
              Text(
                title,
                style: TextStyle(
                  fontFamily: AppConfig.fontFamily,
                  color: AppConfig.primaryColor, // Changed to primary color
                  fontSize: 16,
                ),
              ),
            ],
          ),
          Icon(
            Icons.arrow_forward,
            color: AppConfig.primaryColor, // Changed to primary color
          ),
        ],
      ),
    );
  }
}
