import 'dart:convert';
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
  String _address = 'Fetching location...';
  String _greeting = '......';
  String? _weatherIconUrl;
  int _selectedIndex = 0;
  FieldInfoModel? _selectedField;
  String? _temperature;
  String? _weatherDescription;
  UserModel? _currentUser;
  bool _isLoadingUser = true;

  // OpenWeatherMap API key
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
        print('No user ID found in SharedPreferences');
        setState(() {
          _currentUser = null;
          _isLoadingUser = false;
        });
        return;
      }

      print('Fetching user data for ID: $userId');
      final userService = UserService();
      final user = await userService.getUserData(userId);
      print('Fetched user data: ${user.toMap()}');

      setState(() {
        _currentUser = user;
        _isLoadingUser = false;
      });
    } catch (e) {
      print('Error fetching user data: $e');
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
            style: const TextStyle(fontFamily: AppConfig.fontFamily),
          ),
          content: Text(
            AppLocalizations.of(context)!.locationServiceDisabledMessage,
            style: const TextStyle(fontFamily: AppConfig.fontFamily),
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(context).pop();
              },
              child: Text(
                AppLocalizations.of(context)!.ok,
                style: const TextStyle(fontFamily: AppConfig.fontFamily),
              ),
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
        _address = AppLocalizations.of(context)!.errorGettingLocation(e.toString());
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
        Placemark place = placemarks[0];
        setState(() {
          _address = '${place.locality}, ${place.administrativeArea}';
          _greeting = _getGreeting();
        });
      }
    } catch (e) {
      setState(() {
        _address = AppLocalizations.of(context)!.errorGettingAddress(e.toString());
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
          _weatherDescription = _capitalize(data['weather'][0]['description']);
          _temperature = '${data['main']['temp'].round()}°C';
          _weatherIconUrl =
              'http://openweathermap.org/img/wn/${data['weather'][0]['icon']}@2x.png';
        });
      } else {
        setState(() {
          _weatherDescription = AppLocalizations.of(context)!.weatherUnavailable;
          _temperature = '--°C';
        });
      }
    } catch (e) {
      setState(() {
        _weatherDescription = AppLocalizations.of(context)!.errorLoadingWeather;
        _temperature = '--°C';
      });
    }
  }

  String _capitalize(String text) {
    if (text.isEmpty) return text;
    return '${text[0].toUpperCase()}${text.substring(1)}';
  }

  String _getGreeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) return AppLocalizations.of(context)!.goodMorning;
    if (hour < 18) return AppLocalizations.of(context)!.goodAfternoon;
    return AppLocalizations.of(context)!.goodEvening;
  }

  void _onItemTapped(int index) {
    if (_selectedIndex == index) return;

    setState(() {
      _selectedIndex = index;
    });

    switch (index) {
      case 0:
        break;
      case 1:
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => DashboardScreen(selectedField: _selectedField),
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
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Welcome User Name
              _isLoadingUser
                  ? Text(
                      AppLocalizations.of(context)!.loadingUser,
                      style: TextStyle(
                        fontFamily: AppConfig.fontFamily,
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: AppConfig.primaryColor,
                      ),
                    )
                  : Text(
                      AppLocalizations.of(context)!.welcomeUser(
                        _currentUser?.fullName.isNotEmpty == true
                            ? _currentUser!.fullName
                            : AppLocalizations.of(context)!.defaultUser,
                      ),
                      style: TextStyle(
                        fontFamily: AppConfig.fontFamily,
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        foreground: Paint()
                          ..shader = LinearGradient(
                            colors: [
                              AppConfig.primaryColor,
                              AppConfig.primaryColor.withOpacity(0.8),
                            ],
                          ).createShader(const Rect.fromLTWH(0, 0, 200, 70)),
                      ),
                    ),
              const SizedBox(height: 16),

              // Select Field and Add New Field Buttons
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => SelectFieldDropdown(
                              onFieldSelected: (FieldInfoModel? field) {
                                setState(() {
                                  _selectedField = field;
                                });
                                _saveSelectedField(field);
                              },
                            ),
                          ),
                        );
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppConfig.primaryColor,
                        side: BorderSide(color: AppConfig.primaryColor),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(
                            Icons.arrow_drop_down,
                            color: Colors.white,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            AppLocalizations.of(context)!.selectField,
                            style: const TextStyle(
                              fontFamily: AppConfig.fontFamily,
                              fontSize: 15,
                              color: Colors.white,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) => AddFieldScreen(),
                          ),
                        ).then((_) {
                          setState(() {});
                        });
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppConfig.primaryColor,
                        side: BorderSide(color: AppConfig.primaryColor),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(
                            Icons.add,
                            color: Colors.white,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            AppLocalizations.of(context)!.addNewField,
                            style: const TextStyle(
                              fontFamily: AppConfig.fontFamily,
                              fontSize: 15,
                              color: Colors.white,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Selected Field and Location/Weather Row
              Row(
                children: [
                  // Selected Field Rectangle
                  Expanded(
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(
                          color: AppConfig.primaryColor,
                          width: 1,
                        ),
                      ),
                      child: Text(
                        _selectedField?.fieldName ??
                            AppLocalizations.of(context)!.noFieldSelected,
                        style: TextStyle(
                          fontFamily: AppConfig.fontFamily,
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: AppConfig.primaryColor,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  // Location and Weather Rectangle
                  Expanded(
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(
                          color: AppConfig.primaryColor,
                          width: 1,
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.location_on,
                                color: AppConfig.primaryColor,
                                size: 20,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  _address,
                                  style: TextStyle(
                                    fontFamily: AppConfig.fontFamily,
                                    fontSize: 14,
                                    fontWeight: FontWeight.w500,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              if (_weatherIconUrl != null)
                                Container(
                                  width: 24,
                                  height: 24,
                                  child: ClipRRect(
                                    borderRadius: BorderRadius.circular(4),
                                    child: Image.network(
                                      _weatherIconUrl!,
                                      fit: BoxFit.cover,
                                      errorBuilder: (context, error, stackTrace) =>
                                          Icon(
                                        Icons.cloud,
                                        size: 20,
                                        color: Colors.grey,
                                      ),
                                    ),
                                  ),
                                ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      _weatherDescription ??
                                          AppLocalizations.of(context)!.weather,
                                      style: TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        fontSize: 12,
                                        color: Colors.black87,
                                      ),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                    Text(
                                      _temperature ?? '--°C',
                                      style: TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        fontSize: 14,
                                        fontWeight: FontWeight.bold,
                                        color: Colors.black,
                                      ),
                                    ),
                                  ],
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
              const SizedBox(height: 16),

              // Horizontal Line
              Container(
                height: 1,
                width: double.infinity,
                color: AppConfig.primaryColor,
              ),
              const SizedBox(height: 16),

              // Manage Your Fields Text
              Text(
                'Manage your fields',
                style: TextStyle(
                  fontFamily: AppConfig.fontFamily,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppConfig.primaryColor,
                ),
              ),
              const SizedBox(height: 16),
              // Fertility Mapping Section
              GestureDetector(
                onTap: () {
                  if (_selectedField != null) {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) =>
                            SoilReportScreen(fieldId: _selectedField!.id),
                      ),
                    );
                  } else {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          AppLocalizations.of(context)!.pleaseSelectAFieldFirst,
                        ),
                        backgroundColor: Colors.black,
                      ),
                    );
                  }
                },
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: AppConfig.primaryColor,
                      width: 1,
                    ),
                    gradient: const LinearGradient(
                      begin: Alignment.centerLeft,
                      end: Alignment.centerRight,
                      colors: [Colors.white, Color.fromARGB(255, 139, 254, 229)],
                    ),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Icon
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AppConfig.primaryColor.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(
                          Icons.satellite_alt,
                          color: AppConfig.primaryColor,
                          size: 24,
                        ),
                      ),
                      const SizedBox(width: 12),
                      // Content
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Get a detailed analysis of soil nutrients and parameters with health score',
                              style: TextStyle(
                                fontFamily: AppConfig.fontFamily,
                                fontSize: 14,
                                color: Colors.grey[600],
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Soil Report',
                              style: TextStyle(
                                fontFamily: AppConfig.fontFamily,
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: Colors.black,
                              ),
                            ),
                            const SizedBox(height: 12),
                            // View Map Button
                            Row(
                              children: [
                                Expanded(
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 12,
                                      vertical: 8,
                                    ),
                                    decoration: BoxDecoration(
                                      border: Border.all(
                                        color: Colors.black,
                                        width: 1,
                                      ),
                                      borderRadius: BorderRadius.circular(20),
                                      color: Colors.white,
                                    ),
                                    child: Row(
                                      mainAxisAlignment: MainAxisAlignment.center,
                                      children: [
                                        Text(
                                          'View Report',
                                          style: TextStyle(
                                            fontFamily: AppConfig.fontFamily,
                                            fontSize: 14,
                                            fontWeight: FontWeight.w500,
                                            color: Colors.black,
                                          ),
                                        ),
                                        const SizedBox(width: 8),
                                        const Icon(
                                          Icons.arrow_forward,
                                          size: 16,
                                          color: Colors.black,
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
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Market Analysis Section
              GestureDetector(
                onTap: () {
                  if (_selectedField != null) {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) =>
                            SatelliteMappingScreen(fieldId: _selectedField!.id),
                      ),
                    );
                  } else {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          AppLocalizations.of(context)!.pleaseSelectAFieldFirst,
                        ),
                        backgroundColor: Colors.black,
                      ),
                    );
                  }
                },
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: AppConfig.primaryColor,
                      width: 1,
                    ),
                    gradient: const LinearGradient(
                      begin: Alignment.centerLeft,
                      end: Alignment.centerRight,
                      colors: [Colors.white, Color(0xFFFEF98B)],
                    ),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Icon
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AppConfig.primaryColor.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(
                          Icons.storefront,
                          color: AppConfig.primaryColor,
                          size: 24,
                        ),
                      ),
                      const SizedBox(width: 12),
                      // Content
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Get zone-wise fertility map on your selected field',
                              style: TextStyle(
                                fontFamily: AppConfig.fontFamily,
                                fontSize: 14,
                                color: Colors.grey[600],
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Fertility Mapping',
                              style: TextStyle(
                                fontFamily: AppConfig.fontFamily,
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                                color: Colors.black,
                              ),
                            ),
                            const SizedBox(height: 12),
                            // View Analysis Button
                            Row(
                              children: [
                                Expanded(
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 12,
                                      vertical: 8,
                                    ),
                                    decoration: BoxDecoration(
                                      border: Border.all(
                                        color: Colors.black,
                                        width: 1,
                                      ),
                                      borderRadius: BorderRadius.circular(20),
                                      color: Colors.white,
                                    ),
                                    child: Row(
                                      mainAxisAlignment: MainAxisAlignment.center,
                                      children: [
                                        Text(
                                          'View Map',
                                          style: TextStyle(
                                            fontFamily: AppConfig.fontFamily,
                                            fontSize: 14,
                                            fontWeight: FontWeight.w500,
                                            color: Colors.black,
                                          ),
                                        ),
                                        const SizedBox(width: 8),
                                        const Icon(
                                          Icons.arrow_forward,
                                          size: 16,
                                          color: Colors.black,
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
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 25),
            ],
          ),
        ),
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
        onTap: _onItemTapped,
        showSelectedLabels: true,
        showUnselectedLabels: true,
        selectedItemColor: AppConfig.primaryColor,
        unselectedItemColor: const Color(0xFF757575),
        elevation: 8,
        iconSize: 24,
        selectedLabelStyle: const TextStyle(fontFamily: AppConfig.fontFamily),
        unselectedLabelStyle: const TextStyle(fontFamily: AppConfig.fontFamily),
      ),
    );
  }
}






