import 'dart:convert';
import 'package:farmmatrix/screens/book_appointment/book_appointment.dart';
import 'package:farmmatrix/screens/chatbot/chatbot_screen.dart';
import 'package:farmmatrix/screens/health_history/soil_health_history.dart';
import 'package:farmmatrix/screens/soil_report/soil_report_screen.dart';
import 'package:flutter/material.dart';
import 'package:farmmatrix/config/app_config.dart';
import 'package:geolocator/geolocator.dart';
import 'package:geocoding/geocoding.dart';
import 'package:farmmatrix/screens/dashboard/dashboard.dart';
import 'package:farmmatrix/screens/profile/profile_screen.dart';
import 'package:farmmatrix/screens/field_add_selection/add_field_screen.dart';
import 'package:farmmatrix/screens/field_add_selection/select_field_dropdown.dart';
import 'package:farmmatrix/models/field_info_model.dart';
import 'package:farmmatrix/models/user_model.dart';
import 'package:farmmatrix/services/user_service.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http/http.dart' as http;
import 'package:farmmatrix/screens/mapping/satellite_mapping_screen.dart';
import 'package:farmmatrix/l10n/app_localizations.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String _address = '';
  int _selectedIndex = 0;
  FieldInfoModel? _selectedField;
  String? _temperature;
  UserModel? _currentUser;
  bool _isLoadingUser = true;

  final String _apiKey = 'bfd90807d20e8b889145cbc80b8015b3';

  @override
  void initState() {
    super.initState();
    _loadSelectedField();
    _checkLocationServices();
    _fetchCurrentUser();
  }

  Future<void> _fetchCurrentUser() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final userId = prefs.getString('userId');

      if (userId == null) {
        setState(() {
          _currentUser = null;
          _isLoadingUser = false;
        });
        return;
      }

      final userService = UserService();
      final user = await userService.getUserData(userId);

      setState(() {
        _currentUser = user;
        _isLoadingUser = false;
      });
    } catch (e) {
      setState(() {
        _currentUser = null;
        _isLoadingUser = false;
      });
    }
  }

  Future<void> _loadSelectedField() async {
    final prefs = await SharedPreferences.getInstance();
    final fieldJson = prefs.getString('selectedField');
    if (fieldJson != null) {
      try {
        final fieldMap = jsonDecode(fieldJson) as Map<String, dynamic>;
        setState(() {
          _selectedField = FieldInfoModel.fromMap(fieldMap);
        });
      } catch (e) {
        print('Error decoding saved field: $e');
      }
    }
  }

  Future<void> _saveSelectedField(FieldInfoModel? field) async {
    final prefs = await SharedPreferences.getInstance();
    if (field != null) {
      final fieldJson = jsonEncode(field.toMap());
      await prefs.setString('selectedField', fieldJson);
    } else {
      await prefs.remove('selectedField');
    }
  }

  Future<void> _checkLocationServices() async {
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      _showLocationDialog();
    } else {
      _getCurrentLocation();
    }
  }

  void _showLocationDialog() {
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: Text(
            AppLocalizations.of(context)!.locationServiceDisabledTitle,
          ),
          content: Text(
            AppLocalizations.of(context)!.locationServiceDisabledMessage,
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(AppLocalizations.of(context)!.ok),
            ),
          ],
        );
      },
    );
  }

  Future<void> _getCurrentLocation() async {
    try {
      Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );
      await Future.wait([
        _getAddressFromLatLng(position),
        _fetchWeatherData(position.latitude, position.longitude),
      ]);
    } catch (e) {
      setState(() {
        _address = 'Error getting location';
      });
    }
  }

  Future<void> _getAddressFromLatLng(Position position) async {
    try {
      List<Placemark> placemarks = await placemarkFromCoordinates(
        position.latitude,
        position.longitude,
      );

      if (placemarks.isNotEmpty) {
        Placemark place = placemarks.first;

        String city =
            place.locality ??
            place.subAdministrativeArea ??
            place.subLocality ??
            'Unknown';

        // 🔥 Remove state if accidentally included
        if (city.contains(',')) {
          city = city.split(',').first.trim();
        }

        setState(() {
          _address = city;
        });
      }
    } catch (e) {
      setState(() {
        _address = 'Unknown';
      });
    }
  }

  Future<void> _fetchWeatherData(double lat, double lon) async {
    try {
      final url = Uri.parse(
        'https://api.openweathermap.org/data/2.5/weather?lat=$lat&lon=$lon&appid=$_apiKey&units=metric',
      );

      final response = await http.get(url);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        setState(() {
          _temperature = '${data['main']['temp'].round()}°C';
        });
      } else {
        setState(() {
          _temperature = '--°C';
        });
      }
    } catch (e) {
      setState(() {
        _temperature = '--°C';
      });
    }
  }

  void _onItemTapped(int index) {
    if (_selectedIndex == index) return;

    setState(() => _selectedIndex = index);

    switch (index) {
      case 0:
        break;
      case 1:
        Navigator.push(
          context,
          MaterialPageRoute(
            builder:
                (context) => DashboardScreen(selectedField: _selectedField),
          ),
        );
        break;
      case 2:
        Navigator.push(
          context,
          MaterialPageRoute(builder: (context) => const ProfileScreen()),
        );
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;

    return Scaffold(
      backgroundColor: const Color(0xFFF5F5F5),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            children: [
              // Header Image
              Container(
                height: 210,
                width: double.infinity,
                color: Colors.white,
                child: Image.asset(
                  'assets/images/header_image.png',
                  fit: BoxFit.contain,
                  alignment: Alignment.center,
                ),
              ),

              // Overlapping White Welcome Card
              Transform.translate(
                offset: const Offset(0, -30),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  child: Container(
                    padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(28),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.10),
                          blurRadius: 20,
                          offset: const Offset(0, 10),
                        ),
                      ],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Welcome + cloud
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.center,
                          children: [
                            /// LEFT SIDE → Cloud + Welcome
                            Row(
                              children: [
                                Image.asset(
                                  'assets/images/cloud.png',
                                  width: 22,
                                  height: 22,
                                  fit: BoxFit.contain,
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  _isLoadingUser
                                      ? loc.loading
                                      : loc.welcomeUser(
                                        _currentUser?.fullName ??
                                            loc.defaultUser,
                                      ),
                                  style: const TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                    color: Color(0xFF1B413C),
                                  ),
                                ),
                              ],
                            ),

                            const Spacer(),

                            /// RIGHT SIDE → Location + Weather + Temp
                            Row(
                              children: [
                                const Icon(
                                  Icons.location_on,
                                  size: 16,
                                  color: Color(0xFF1B413C),
                                ),

                                const SizedBox(width: 4),

                                Text(
                                  '$_address ${_temperature ?? ''}',
                                  style: const TextStyle(
                                    fontSize: 13,
                                    color: Color(0xFF1B413C),
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),

                        const SizedBox(height: 15),

                        // Current Field
                        Center(
                          child: Column(
                            children: [
                              Text(
                                loc.currentField,
                                style: const TextStyle(
                                  fontSize: 14,
                                  color: Color(0xFF1B413C),
                                ),
                              ),
                              const SizedBox(height: 6),
                              Text(
                                _selectedField?.fieldName ??
                                    loc.noFieldSelected,
                                style: const TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                  color: Color(0xFF1B413C),
                                ),
                                textAlign: TextAlign.center,
                              ),
                            ],
                          ),
                        ),

                        const SizedBox(height: 12),

                        // Select & Add buttons
                        Row(
                          children: [
                            Expanded(
                              child: _FieldActionButton(
                                label: loc.selectField,
                                backgroundColor: const Color(0xFFD9D9D9),
                                icon: Icons.arrow_drop_down,
                                onPressed: () {
                                  Navigator.push(
                                    context,
                                    MaterialPageRoute(
                                      builder:
                                          (context) => SelectFieldDropdown(
                                            onFieldSelected: (field) {
                                              setState(
                                                () => _selectedField = field,
                                              );
                                              _saveSelectedField(field);
                                            },
                                          ),
                                    ),
                                  );
                                },
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: _FieldActionButton(
                                label: loc.addNewField,
                                backgroundColor: const Color(0xFFFFD358),
                                icon: Icons.add,
                                textColor: Colors.black87,
                                onPressed: () {
                                  Navigator.push(
                                    context,
                                    MaterialPageRoute(
                                      builder: (_) => const AddFieldScreen(),
                                    ),
                                  ).then((_) => setState(() {}));
                                },
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              // Feature Cards
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Column(
                  children: [
                    FeatureCard(
                      bgImagePath: 'assets/images/soil_bg.jpeg',
                      iconPath: 'assets/images/soil_report.png',
                      title: loc.soilReportTitle,
                      description: loc.soilReportDescription,
                      buttonLabel: loc.viewReport,
                      onTap: () {
                        if (_selectedField != null) {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder:
                                  (_) => SoilReportScreen(
                                    fieldId: _selectedField!.id,
                                  ),
                            ),
                          );
                        } else {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(loc.pleaseSelectAFieldFirst),
                            ),
                          );
                        }
                      },
                    ),
                    const SizedBox(height: 24),
                    FeatureCard(
                      bgImagePath: 'assets/images/fertility_bg.jpeg',
                      iconPath: 'assets/images/fertility.png',
                      title: loc.fertilityMappingTitle,
                      description: loc.fertilityMappingDescription,
                      buttonLabel: loc.viewMap,
                      onTap: () {
                        if (_selectedField != null) {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder:
                                  (_) => SatelliteMappingScreen(
                                    fieldId: _selectedField!.id,
                                  ),
                            ),
                          );
                        } else {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(loc.pleaseSelectAFieldFirst),
                            ),
                          );
                        }
                      },
                    ),
                    const SizedBox(height: 24),
                    FeatureCard(
                      bgImagePath: 'assets/images/health_history_bg.jpeg',
                      iconPath: 'assets/images/health_history.png',
                      title: loc.soilHealthHistoryTitle,
                      description: loc.soilHealthHistoryDescription,
                      buttonLabel: loc.viewHistory,
                      onTap: () {
                        if (_selectedField != null) {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder:
                                  (_) => SoilHealthHistoryScreen(
                                    fieldId: _selectedField!.id,
                                  ),
                            ),
                          );
                        } else {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(loc.pleaseSelectAFieldFirst),
                            ),
                          );
                        }
                      },
                    ),

                    const SizedBox(height: 24),
                    FeatureCard(
                      bgImagePath: 'assets/images/book_appointment.png',
                      iconPath: 'assets/images/book_appoint.png',
                      title: loc.bookAppointmentTitle,
                      description: loc.bookAppointmentDescription,
                      buttonLabel: loc.scheduleNow,
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => const BookAppointmentScreen(),
                          ),
                        );
                      },
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 80), // space for FAB
            ],
          ),
        ),
      ),

      floatingActionButton: FloatingActionButton(
        elevation: 0,
        backgroundColor: Colors.transparent,
        highlightElevation: 0,
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const ChatbotScreen()),
          );
        },
        child: Transform.scale(
          scale: 1.5,
          child: Image.asset(
            'assets/images/chatbot.png',
            width: 60,
            height: 60,
          ),
        ),
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.endFloat,

      bottomNavigationBar: _CustomBottomBar(
        selectedIndex: _selectedIndex,
        onItemTapped: _onItemTapped,
      ),
    );
  }
}

class _CustomBottomBar extends StatelessWidget {
  final int selectedIndex;
  final Function(int) onItemTapped;

  const _CustomBottomBar({
    required this.selectedIndex,
    required this.onItemTapped,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 80,
      margin: const EdgeInsets.only(left: 20, right: 20, bottom: 15),
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.center,
        children: [
          // Green rounded bar
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: Container(
              height: 60,
              decoration: BoxDecoration(
                color: const Color(0xFF1B413C),
                borderRadius: BorderRadius.circular(40),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  // Home
                  IconButton(
                    onPressed: () => onItemTapped(0),
                    icon: Icon(
                      Icons.home_outlined,
                      color: selectedIndex == 0 ? Colors.white : Colors.white70,
                      size: 28,
                    ),
                  ),

                  const SizedBox(width: 60), // space for center button
                  // Profile
                  IconButton(
                    onPressed: () => onItemTapped(2),
                    icon: Icon(
                      Icons.person_outline,
                      color: selectedIndex == 2 ? Colors.white : Colors.white70,
                      size: 28,
                    ),
                  ),
                ],
              ),
            ),
          ),

          // Center Yellow Dashboard Button
          Positioned(
            top: -15,
            child: GestureDetector(
              onTap: () => onItemTapped(1),
              child: Container(
                width: 90,
                height: 90,
                decoration: const BoxDecoration(
                  color: Color(0xFFFFD358),
                  shape: BoxShape.circle,
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.dashboard_outlined,
                      size: 30,
                      color: Colors.black87,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      AppLocalizations.of(context)!.dashboardLabel,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: Colors.black87,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// Reusable Field Action Button
class _FieldActionButton extends StatelessWidget {
  final String label;
  final Color backgroundColor;
  final IconData icon;
  final Color? textColor;
  final VoidCallback onPressed;

  const _FieldActionButton({
    required this.label,
    required this.backgroundColor,
    required this.icon,
    this.textColor,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: onPressed,
      style: ElevatedButton.styleFrom(
        backgroundColor: backgroundColor,
        foregroundColor: textColor ?? Colors.black87,
        padding: const EdgeInsets.symmetric(vertical: 12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        elevation: 0,
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 22),
          const SizedBox(width: 10),
          Text(
            label,
            style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}

// Updated FeatureCard with overlap & overflow fixes
class FeatureCard extends StatelessWidget {
  final String bgImagePath;
  final String iconPath;
  final String title;
  final String description;
  final String buttonLabel;
  final VoidCallback onTap;

  const FeatureCard({
    super.key,
    required this.bgImagePath,
    required this.iconPath,
    required this.title,
    required this.description,
    required this.buttonLabel,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 270, // increased to give more vertical space
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.08),
              blurRadius: 12,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: Stack(
            clipBehavior: Clip.none,
            children: [
              // Background image
              Positioned.fill(
                child: Image.asset(
                  bgImagePath,
                  fit: BoxFit.cover,
                  alignment: Alignment.topCenter,
                ),
              ),

              // White bottom section – taller and more padding
              Positioned(
                bottom: 0,
                left: 0,
                right: 0,
                height: 151, // increased from 150 → fixes overflow
                child: Container(
                  padding: const EdgeInsets.fromLTRB(
                    16,
                    20,
                    16,
                    16,
                  ), // more top space
                  decoration: const BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.vertical(
                      bottom: Radius.circular(20),
                    ),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Left content – description now wraps properly
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              title,
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: Color(0xFF2A2A2A),
                              ),
                            ),
                            const SizedBox(height: 6),
                            Flexible(
                              child: Text(
                                description,
                                softWrap: true,
                                style: TextStyle(
                                  fontSize: 13,
                                  color: Colors.grey[700],
                                  height: 1.35,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),

                      // Right side: circle + pill
                      Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          // Yellow circle – still overlaps background, but safer value
                          Transform.translate(
                            offset: const Offset(
                              0,
                              -40,
                            ), // was -36 → slightly less aggressive
                            child: Container(
                              width: 72,
                              height: 72,
                              decoration: const BoxDecoration(
                                color: Color(0xFFFFD358),
                                shape: BoxShape.circle,
                              ),
                              child: Center(
                                child: Image.asset(
                                  iconPath,
                                  width: 44,
                                  height: 44,
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 8),

                          // Pill – moved up but not too much → no overflow
                          Transform.translate(
                            offset: const Offset(
                              0,
                              -22,
                            ), // was -28 → safer value
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 16,
                                vertical: 8,
                              ),
                              decoration: BoxDecoration(
                                color: const Color(0xFFD9D9D9),
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(
                                    buttonLabel,
                                    style: const TextStyle(
                                      fontSize: 10,
                                      fontWeight: FontWeight.w600,
                                      color: Colors.black87,
                                    ),
                                  ),
                                  const SizedBox(width: 6),
                                  const Icon(
                                    Icons.arrow_forward,
                                    size: 16,
                                    color: Colors.black87,
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
