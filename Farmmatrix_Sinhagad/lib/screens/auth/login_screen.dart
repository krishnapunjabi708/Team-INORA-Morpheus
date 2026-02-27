import 'package:flutter/material.dart';
import 'package:farmmatrix/config/app_config.dart';
import 'package:farmmatrix/screens/home/home_screen.dart';
import 'package:farmmatrix/l10n/app_localizations.dart'; // Use generated localizations
import 'package:farmmatrix/widgets/common_widgets.dart';
import 'package:farmmatrix/services/auth_services.dart';
import 'package:geolocator/geolocator.dart';
import 'package:country_code_picker/country_code_picker.dart';
import 'package:shared_preferences/shared_preferences.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({Key? key}) : super(key: key);

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  String _countryCode = '+91';
  bool _isLoading = false;

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  Future<void> _handleLogin() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    try {
      // 1. Check and request location permissions
      await _checkLocationPermissions();

      // 2. Get current position
      final Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );

      // 3. Create full phone number
      final String fullPhoneNumber = '$_countryCode${_phoneController.text}';

      // 4. Create or get existing user in database
      final userId = await AuthServices.createUser(
        phone: fullPhoneNumber,
        fullName: _nameController.text,
        latitude: position.latitude,
        longitude: position.longitude,
      );

      // 5. Verify user was created or exists
      if (userId == null) {
        throw Exception('User creation failed');
      }

      // 6. Store userId in SharedPreferences
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('userId', userId);

      // 7. Navigate to home screen
      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (context) => const HomeScreen()),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: ${e.toString()}')),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _checkLocationPermissions() async {
    // Check if location service is enabled
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      // Location services are not enabled, ask user to enable them
      bool? shouldOpenSettings = await showDialog(
        context: context,
        builder: (BuildContext context) {
          return AlertDialog(
            title: Text(AppLocalizations.of(context)!.locationServiceDisabledTitle),
            content: Text(AppLocalizations.of(context)!.locationServiceDisabledMessage),
            actions: <Widget>[
              TextButton(
                child: Text(AppLocalizations.of(context)!.cancel),
                onPressed: () => Navigator.of(context).pop(false),
              ),
              TextButton(
                child: Text(AppLocalizations.of(context)!.openSettings),
                onPressed: () => Navigator.of(context).pop(true),
              ),
            ],
          );
        },
      );

      if (shouldOpenSettings == true) {
        await Geolocator.openLocationSettings();
        // Check again after returning from settings
        serviceEnabled = await Geolocator.isLocationServiceEnabled();
        if (!serviceEnabled) {
          throw Exception(AppLocalizations.of(context)!.locationServicesStillDisabled);
        }
      } else {
        throw Exception(AppLocalizations.of(context)!.locationServicesRequired);
      }
    }

    // Check location permissions
    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        // Show dialog explaining why we need permissions
        bool? shouldOpenSettings = await showDialog(
          context: context,
          builder: (BuildContext context) {
            return AlertDialog(
              title: Text(AppLocalizations.of(context)!.locationPermissionRequiredTitle),
              content: Text(AppLocalizations.of(context)!.locationPermissionRequiredMessage),
              actions: <Widget>[
                TextButton(
                  child: Text(AppLocalizations.of(context)!.cancel),
                  onPressed: () => Navigator.of(context).pop(false),
                ),
                TextButton(
                  child: Text(AppLocalizations.of(context)!.openSettings),
                  onPressed: () => Navigator.of(context).pop(true),
                ),
              ],
            );
          },
        );

        if (shouldOpenSettings == true) {
          await Geolocator.openAppSettings();
          // Check again after returning from settings
          permission = await Geolocator.checkPermission();
          if (permission == LocationPermission.denied) {
            throw Exception(AppLocalizations.of(context)!.locationPermissionsStillDenied);
          }
        } else {
          throw Exception(AppLocalizations.of(context)!.locationPermissionsStillDenied);
        }
      }
    }

    if (permission == LocationPermission.deniedForever) {
      // The user opted to never again see the permission request dialog
      bool? shouldOpenSettings = await showDialog(
        context: context,
        builder: (BuildContext context) {
          return AlertDialog(
            title: Text(AppLocalizations.of(context)!.locationPermissionPermanentlyDeniedTitle),
            content: Text(AppLocalizations.of(context)!.locationPermissionPermanentlyDeniedMessage),
            actions: <Widget>[
              TextButton(
                child: Text(AppLocalizations.of(context)!.cancel),
                onPressed: () => Navigator.of(context).pop(false),
              ),
              TextButton(
                child: Text(AppLocalizations.of(context)!.openSettings),
                onPressed: () => Navigator.of(context).pop(true),
              ),
           ],
          );
        },
      );

      if (shouldOpenSettings == true) {
        await Geolocator.openAppSettings();
        // Check again after returning from settings
        permission = await Geolocator.checkPermission();
        if (permission == LocationPermission.denied ||
            permission == LocationPermission.deniedForever) {
          throw Exception(AppLocalizations.of(context)!.locationPermissionsPermanentlyDenied);
        }
      } else {
        throw Exception(AppLocalizations.of(context)!.locationPermissionsPermanentlyDenied);
      }
    }
  }

 @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;

    return Scaffold(
      extendBodyBehindAppBar: true,
      body: Stack(
        children: [

          /// Background Image
          SizedBox.expand(
            child: Image.asset(
              "assets/images/login_bg.png",
              fit: BoxFit.cover,
            ),
          ),

          /// Content
          SafeArea(
            child: SingleChildScrollView(
              padding:
                  const EdgeInsets.symmetric(
                      horizontal: 24),
              child: Column(
                children: [

                  const SizedBox(height: 80),

                  /// Logo
                  Image.asset(
                    'assets/images/logo.png',
                    width: 180,
                  ),

                  const SizedBox(height: 40),

                  /// Login Heading
                  Text(
                    loc.logIn,
                    style: const TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),

                  const SizedBox(height: 30),

                  /// Form
                  Form(
                    key: _formKey,
                    child: Column(
                      children: [

                        /// Full Name
                        TextFormField(
                          controller:
                              _nameController,
                          decoration:
                              _inputDecoration(
                            hint: loc.fullName,
                            icon: Icons.person,
                          ),
                          validator: (value) {
                            if (value == null ||
                                value.isEmpty) {
                              return loc
                                  .pleaseEnterName;
                            }
                            return null;
                          },
                        ),

                        const SizedBox(height: 16),

                        /// Phone Row
                        Row(
                          children: [

                            /// Country Code
                            Container(
                              padding:
                                  const EdgeInsets
                                      .symmetric(
                                      horizontal:
                                          6),
                              decoration:
                                  BoxDecoration(
                                color: Colors.white,
                                borderRadius:
                                    BorderRadius
                                        .circular(
                                            12),
                              ),
                              child:
                                  CountryCodePicker(
                                onChanged:
                                    (code) {
                                  _countryCode =
                                      code.dialCode!;
                                },
                                initialSelection:
                                    'IN',
                                alignLeft: false,
                              ),
                            ),

                            const SizedBox(width: 10),

                            /// Phone Number
                            Expanded(
                              child:
                                  TextFormField(
                                controller:
                                    _phoneController,
                                keyboardType:
                                    TextInputType
                                        .phone,
                                decoration:
                                    _inputDecoration(
                                  hint:
                                      loc.phoneNo,
                                  icon:
                                      Icons.phone,
                                ),
                                validator:
                                    (value) {
                                  if (value ==
                                          null ||
                                      value
                                          .isEmpty) {
                                    return loc
                                        .pleaseEnterPhoneNumber;
                                  }
                                  if (value
                                          .length <
                                      10) {
                                    return loc
                                        .invalidPhoneNumber;
                                  }
                                  return null;
                                },
                              ),
                            ),
                          ],
                        ),

                        const SizedBox(height: 30),

                        /// Login Button
                        PrimaryButton(
                          text: _isLoading
                              ? loc.processing
                              : loc.logIn,
                          onPressed: _isLoading
                              ? () {}
                              : _handleLogin,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  InputDecoration _inputDecoration({
    required String hint,
    required IconData icon,
  }) {
    return InputDecoration(
      filled: true,
      fillColor: Colors.white,
      hintText: hint,
      prefixIcon:
          Icon(icon, color: Colors.black54),
      border: OutlineInputBorder(
        borderRadius:
            BorderRadius.circular(12),
        borderSide: BorderSide.none,
      ),
      contentPadding:
          const EdgeInsets.symmetric(
              vertical: 16),
    );
  }
}