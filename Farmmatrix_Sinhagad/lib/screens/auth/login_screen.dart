// import 'package:flutter/material.dart';
// import 'package:farmmatrix/config/app_config.dart';
// import 'package:farmmatrix/screens/home/home_screen.dart';
// import 'package:farmmatrix/utils/app_localizations.dart';
// import 'package:farmmatrix/widgets/common_widgets.dart';
// import 'package:farmmatrix/services/auth_services.dart';
// import 'package:geolocator/geolocator.dart';
// import 'package:country_code_picker/country_code_picker.dart';
// import 'package:shared_preferences/shared_preferences.dart';

// class LoginScreen extends StatefulWidget {
//   const LoginScreen({Key? key}) : super(key: key);

//   @override
//   State<LoginScreen> createState() => _LoginScreenState();
// }

// class _LoginScreenState extends State<LoginScreen> {
//   final _formKey = GlobalKey<FormState>();
//   final _nameController = TextEditingController();
//   final _phoneController = TextEditingController();
//   String _countryCode = '+91';
//   bool _isLoading = false;

//   @override
//   void dispose() {
//     _nameController.dispose();
//     _phoneController.dispose();
//     super.dispose();
//   }

//   Future<void> _handleLogin() async {
//     if (!_formKey.currentState!.validate()) return;

//     setState(() => _isLoading = true);

//     try {
//       // 1. Check and request location permissions
//       await _checkLocationPermissions();

//       // 2. Get current position
//       final Position position = await Geolocator.getCurrentPosition(
//         desiredAccuracy: LocationAccuracy.high,
//       );

//       // 3. Create full phone number
//       final String fullPhoneNumber = '$_countryCode${_phoneController.text}';

//       // 4. Create or get existing user in database
//       final userId = await AuthServices.createUser(
//         phone: fullPhoneNumber,
//         fullName: _nameController.text,
//         latitude: position.latitude,
//         longitude: position.longitude,
//       );

//       // 5. Verify user was created or exists
//       if (userId == null) {
//         throw Exception('User creation failed');
//       }

//       // 6. Store userId in SharedPreferences
//       final prefs = await SharedPreferences.getInstance();
//       await prefs.setString('userId', userId);

//       // 7. Navigate to home screen
//       if (mounted) {
//         Navigator.pushReplacement(
//           context,
//           MaterialPageRoute(builder: (context) => const HomeScreen()),
//         );
//       }
//     } catch (e) {
//       if (mounted) {
//         ScaffoldMessenger.of(
//           context,
//         ).showSnackBar(SnackBar(content: Text('Error: ${e.toString()}')));
//       }
//     } finally {
//       if (mounted) setState(() => _isLoading = false);
//     }
//   }

//   // Future<void> _checkLocationPermissions() async {
//   //   LocationPermission permission = await Geolocator.checkPermission();
//   //   if (permission == LocationPermission.denied) {
//   //     permission = await Geolocator.requestPermission();
//   //     if (permission == LocationPermission.denied) {
//   //       throw Exception('Location permissions are denied');
//   //     }
//   //   }

//   //   if (permission == LocationPermission.deniedForever) {
//   //     throw Exception('Location permissions are permanently denied');
//   //   }

//   //   bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
//   //   if (!serviceEnabled) {
//   //     throw Exception('Location services are disabled');
//   //   }
//   // }

//   Future<void> _checkLocationPermissions() async {
//     // Check if location service is enabled
//     bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
//     if (!serviceEnabled) {
//       // Location services are not enabled, ask user to enable them
//       bool? shouldOpenSettings = await showDialog(
//         context: context,
//         builder: (BuildContext context) {
//           return AlertDialog(
//             title: const Text('Location Service Disabled'),
//             content: const Text(
//               'Location services are disabled. Please enable them to continue.',
//             ),
//             actions: <Widget>[
//               TextButton(
//                 child: const Text('Cancel'),
//                 onPressed: () => Navigator.of(context).pop(false),
//               ),
//               TextButton(
//                 child: const Text('Open Settings'),
//                 onPressed: () => Navigator.of(context).pop(true),
//               ),
//             ],
//           );
//         },
//       );

//       if (shouldOpenSettings == true) {
//         await Geolocator.openLocationSettings();
//         // Check again after returning from settings
//         serviceEnabled = await Geolocator.isLocationServiceEnabled();
//         if (!serviceEnabled) {
//           throw Exception('Location services are still disabled');
//         }
//       } else {
//         throw Exception('Location services are required');
//       }
//     }

//     // Check location permissions
//     LocationPermission permission = await Geolocator.checkPermission();
//     if (permission == LocationPermission.denied) {
//       permission = await Geolocator.requestPermission();
//       if (permission == LocationPermission.denied) {
//         // Show dialog explaining why we need permissions
//         bool? shouldOpenSettings = await showDialog(
//           context: context,
//           builder: (BuildContext context) {
//             return AlertDialog(
//               title: const Text('Location Permission Required'),
//               content: const Text(
//                 'We need location permissions to provide better service.',
//               ),
//               actions: <Widget>[
//                 TextButton(
//                   child: const Text('Cancel'),
//                   onPressed: () => Navigator.of(context).pop(false),
//                 ),
//                 TextButton(
//                   child: const Text('Open Settings'),
//                   onPressed: () => Navigator.of(context).pop(true),
//                 ),
//               ],
//             );
//           },
//         );

//         if (shouldOpenSettings == true) {
//           await Geolocator.openAppSettings();
//           // Check again after returning from settings
//           permission = await Geolocator.checkPermission();
//           if (permission == LocationPermission.denied) {
//             throw Exception('Location permissions are still denied');
//           }
//         } else {
//           throw Exception('Location permissions are denied');
//         }
//       }
//     }

//     if (permission == LocationPermission.deniedForever) {
//       // The user opted to never again see the permission request dialog
//       bool? shouldOpenSettings = await showDialog(
//         context: context,
//         builder: (BuildContext context) {
//           return AlertDialog(
//             title: const Text('Location Permission Permanently Denied'),
//             content: const Text(
//               'You have permanently denied location permissions. Please enable them in app settings.',
//             ),
//             actions: <Widget>[
//               TextButton(
//                 child: const Text('Cancel'),
//                 onPressed: () => Navigator.of(context).pop(false),
//               ),
//               TextButton(
//                 child: const Text('Open Settings'),
//                 onPressed: () => Navigator.of(context).pop(true),
//               ),
//             ],
//           );
//         },
//       );

//       if (shouldOpenSettings == true) {
//         await Geolocator.openAppSettings();
//         // Check again after returning from settings
//         permission = await Geolocator.checkPermission();
//         if (permission == LocationPermission.denied ||
//             permission == LocationPermission.deniedForever) {
//           throw Exception('Location permissions are still denied');
//         }
//       } else {
//         throw Exception('Location permissions are permanently denied');
//       }
//     }
//   }

//   @override
//   Widget build(BuildContext context) {
//     return Scaffold(
//       body: Container(
//         decoration: BoxDecoration(gradient: AppConfig.authGradient),
//         child: SafeArea(
//           child: Column(
//             children: [
//               // Logo
//               Padding(
//                 padding: const EdgeInsets.only(top: 35),
//                 child: Image.asset(
//                   'assets/images/logo2.png',
//                   width: 200,
//                   height: 150,
//                 ),
//               ),
//               const SizedBox(height: 70),
//               // White container with login form
//               Expanded(
//                 child: Container(
//                   width: double.infinity,
//                   padding: const EdgeInsets.all(24),
//                   decoration: const BoxDecoration(
//                     color: Color.fromARGB(255, 251, 246, 235),
//                     borderRadius: BorderRadius.only(
//                       topLeft: Radius.circular(30),
//                       topRight: Radius.circular(30),
//                     ),
//                   ),
//                   child: SingleChildScrollView(
//                     child: Column(
//                       crossAxisAlignment: CrossAxisAlignment.start,
//                       children: [
//                         // Login Text
//                         Text(
//                           AppLocalizations.of(context).translate('log_in'),
//                           style: const TextStyle(
//                             fontFamily: AppConfig.fontFamily,
//                             fontSize: 24,
//                             fontWeight: FontWeight.bold,
//                             color: Color.fromARGB(255, 211, 136, 48),
//                           ),
//                         ),
//                         const SizedBox(height: 24),
//                         // Login Form
//                         Form(
//                           key: _formKey,
//                           child: Column(
//                             children: [
//                               // Full Name Field
//                               TextFormField(
//                                 controller: _nameController,
//                                 decoration: InputDecoration(
//                                   filled: true,
//                                   fillColor: AppConfig.accentColor,
//                                   hintText: AppLocalizations.of(
//                                     context,
//                                   ).translate('full_name'),
//                                   prefixIcon: const Icon(
//                                     Icons.person,
//                                     color: Colors.black54,
//                                   ),
//                                   border: OutlineInputBorder(
//                                     borderRadius: BorderRadius.circular(10),
//                                     borderSide: BorderSide.none,
//                                   ),
//                                 ),
//                                 validator: (value) {
//                                   if (value == null || value.isEmpty) {
//                                     return 'Please enter your name';
//                                   }
//                                   return null;
//                                 },
//                               ),
//                               const SizedBox(height: 16),
//                               // Phone Number Field with Country Code
//                               Row(
//                                 children: [
//                                   // Country Code Picker
//                                   Container(
//                                     decoration: BoxDecoration(
//                                       color: AppConfig.accentColor,
//                                       borderRadius: BorderRadius.circular(10),
//                                     ),
//                                     child: CountryCodePicker(
//                                       onChanged: (CountryCode code) {
//                                         setState(() {
//                                           _countryCode = code.dialCode!;
//                                         });
//                                       },
//                                       initialSelection: 'IN',
//                                       favorite: ['+91', 'IN'],
//                                       showCountryOnly: false,
//                                       showOnlyCountryWhenClosed: false,
//                                       alignLeft: false,
//                                       padding: EdgeInsets.zero,
//                                       textStyle: const TextStyle(
//                                         fontFamily: AppConfig.fontFamily,
//                                         color: Colors.black,
//                                       ),
//                                     ),
//                                   ),
//                                   const SizedBox(width: 8),
//                                   // Phone Number Input
//                                   Expanded(
//                                     child: TextFormField(
//                                       controller: _phoneController,
//                                       decoration: InputDecoration(
//                                         filled: true,
//                                         fillColor: AppConfig.accentColor,
//                                         hintText: AppLocalizations.of(
//                                           context,
//                                         ).translate('phone_no'),
//                                         prefixIcon: const Icon(
//                                           Icons.phone,
//                                           color: Colors.black54,
//                                         ),
//                                         border: OutlineInputBorder(
//                                           borderRadius: BorderRadius.circular(
//                                             10,
//                                           ),
//                                           borderSide: BorderSide.none,
//                                         ),
//                                       ),
//                                       keyboardType: TextInputType.phone,
//                                       validator: (value) {
//                                         if (value == null || value.isEmpty) {
//                                           return 'Please enter your phone number';
//                                         }
//                                         if (value.length < 10) {
//                                           return 'Please enter a valid phone number';
//                                         }
//                                         return null;
//                                       },
//                                     ),
//                                   ),
//                                 ],
//                               ),
//                               const SizedBox(height: 24),
//                               // Login Button
//                               SizedBox(
//                                 width: double.infinity,
//                                 child: PrimaryButton(
//                                   text:
//                                       _isLoading
//                                           ? 'Processing...'
//                                           : AppLocalizations.of(
//                                             context,
//                                           ).translate('log_in'),
//                                   onPressed: _isLoading ? () {} : _handleLogin,
//                                 ),
//                               ),
//                             ],
//                           ),
//                         ),
//                       ],
//                     ),
//                   ),
//                 ),
//               ),
//             ],
//           ),
//         ),
//       ),
//     );
//   }
// }



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
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(gradient: AppConfig.authGradient),
        child: SafeArea(
          child: Column(
            children: [
              // Logo
              Padding(
                padding: const EdgeInsets.only(top: 35),
                child: Image.asset(
                  'assets/images/logo2.png',
                  width: 200,
                  height: 150,
                ),
              ),
              const SizedBox(height: 70),
              // White container with login form
              Expanded(
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(24),
                  decoration: const BoxDecoration(
                    color: Color.fromARGB(255, 251, 246, 235),
                    borderRadius: BorderRadius.only(
                      topLeft: Radius.circular(30),
                      topRight: Radius.circular(30),
                    ),
                  ),
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Login Text
                        Text(
                          AppLocalizations.of(context)!.logIn,
                          style: const TextStyle(
                            fontFamily: AppConfig.fontFamily,
                            fontSize: 24,
                            fontWeight: FontWeight.bold,
                            color: Color.fromARGB(255, 211, 136, 48),
                          ),
                        ),
                        const SizedBox(height: 24),
                        // Login Form
                        Form(
                          key: _formKey,
                          child: Column(
                            children: [
                              // Full Name Field
                              TextFormField(
                                controller: _nameController,
                                decoration: InputDecoration(
                                  filled: true,
                                  fillColor: AppConfig.accentColor,
                                  hintText: AppLocalizations.of(context)!.fullName,
                                  prefixIcon: const Icon(
                                    Icons.person,
                                    color: Colors.black54,
                                  ),
                                  border: OutlineInputBorder(
                                    borderRadius: BorderRadius.circular(10),
                                    borderSide: BorderSide.none,
                                  ),
                                ),
                                validator: (value) {
                                  if (value == null || value.isEmpty) {
                                    return AppLocalizations.of(context)!.pleaseEnterName;
                                  }
                                  return null;
                                },
                              ),
                              const SizedBox(height: 16),
                              // Phone Number Field with Country Code
                              Row(
                                children: [
                                  // Country Code Picker
                                  Container(
                                    decoration: BoxDecoration(
                                      color: AppConfig.accentColor,
                                      borderRadius: BorderRadius.circular(10),
                                    ),
                                    child: CountryCodePicker(
                                      onChanged: (CountryCode code) {
                                        setState(() {
                                          _countryCode = code.dialCode!;
                                        });
                                      },
                                      initialSelection: 'IN',
                                      favorite: ['+91', 'IN'],
                                      showCountryOnly: false,
                                      showOnlyCountryWhenClosed: false,
                                      alignLeft: false,
                                      padding: EdgeInsets.zero,
                                      textStyle: const TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        color: Colors.black,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  // Phone Number Input
                                  Expanded(
                                    child: TextFormField(
                                      controller: _phoneController,
                                      decoration: InputDecoration(
                                        filled: true,
                                        fillColor: AppConfig.accentColor,
                                        hintText: AppLocalizations.of(context)!.phoneNo,
                                        prefixIcon: const Icon(
                                          Icons.phone,
                                          color: Colors.black54,
                                        ),
                                        border: OutlineInputBorder(
                                          borderRadius: BorderRadius.circular(10),
                                          borderSide: BorderSide.none,
                                        ),
                                      ),
                                      keyboardType: TextInputType.phone,
                                      validator: (value) {
                                        if (value == null || value.isEmpty) {
                                          return AppLocalizations.of(context)!.pleaseEnterPhoneNumber;
                                        }
                                        if (value.length < 10) {
                                          return AppLocalizations.of(context)!.invalidPhoneNumber;
                                        }
                                        return null;
                                      },
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 24),
                              // Login Button
                              SizedBox(
                                width: double.infinity,
                                child: PrimaryButton(
                                  text: _isLoading
                                      ? AppLocalizations.of(context)!.processing
                                      : AppLocalizations.of(context)!.logIn,
                                  onPressed: _isLoading ? () {} : _handleLogin,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
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