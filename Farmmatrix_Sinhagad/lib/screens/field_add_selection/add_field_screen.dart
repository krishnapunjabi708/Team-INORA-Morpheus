
// import 'package:flutter/material.dart';
// import 'package:google_maps_flutter/google_maps_flutter.dart';
// import 'package:geolocator/geolocator.dart';
// import 'package:geocoding/geocoding.dart';
// import 'package:supabase_flutter/supabase_flutter.dart';
// import 'package:shared_preferences/shared_preferences.dart';
// import 'package:farmmatrix/l10n/app_localizations.dart';

// class AddFieldScreen extends StatefulWidget {
//   const AddFieldScreen({super.key});

//   @override
//   _AddFieldScreenState createState() => _AddFieldScreenState();
// }

// class _AddFieldScreenState extends State<AddFieldScreen> {
//   late GoogleMapController _mapController;
//   LatLng? _currentLocation;
//   final Set<Polygon> _polygons = {};
//   final Set<Marker> _markers = {};
//   final List<LatLng> _polygonPoints = [];
//   final TextEditingController _fieldNameController = TextEditingController();
//   final TextEditingController _searchController = TextEditingController();
//   final SupabaseClient _supabase = Supabase.instance.client;
//   bool _isSaving = false;
//   bool _isConfirmEnabled = false;

//   @override
//   void initState() {
//     super.initState();
//     _getCurrentLocation();
//   }

//   Future<void> _getCurrentLocation() async {
//     try {
//       bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
//       if (!serviceEnabled) {
//         throw Exception(AppLocalizations.of(context)!.locationServicesDisabled);
//       }

//       LocationPermission permission = await Geolocator.checkPermission();
//       if (permission == LocationPermission.denied) {
//         permission = await Geolocator.requestPermission();
//         if (permission == LocationPermission.denied) {
//           throw Exception(AppLocalizations.of(context)!.locationPermissionsDenied);
//         }
//       }

//       Position position = await Geolocator.getCurrentPosition(
//         desiredAccuracy: LocationAccuracy.high,
//       );
//       setState(() {
//         _currentLocation = LatLng(position.latitude, position.longitude);
//       });
//     } catch (e) {
//       ScaffoldMessenger.of(context).showSnackBar(
//         SnackBar(content: Text(AppLocalizations.of(context)!.error(e.toString()))),
//       );
//     }
//   }

//   Future<void> _searchAndNavigate(String query) async {
//     try {
//       List<Location> locations = await locationFromAddress(query);
//       if (locations.isNotEmpty) {
//         final target = LatLng(
//           locations.first.latitude,
//           locations.first.longitude,
//         );
//         _mapController.animateCamera(CameraUpdate.newLatLngZoom(target, 16));
//       } else {
//         ScaffoldMessenger.of(context).showSnackBar(
//           SnackBar(content: Text(AppLocalizations.of(context)!.locationNotFound)),
//         );
//       }
//     } catch (e) {
//       ScaffoldMessenger.of(context).showSnackBar(
//         SnackBar(content: Text(AppLocalizations.of(context)!.searchError(e.toString()))),
//       );
//     }
//   }

//   void _onMapTap(LatLng position) {
//     _polygonPoints.add(position);
//     _isConfirmEnabled = _polygonPoints.length >= 3;
//     _updatePolygon();
//   }

//   void _updatePolygon() {
//     _polygons.clear();
//     _markers.clear();

//     for (int i = 0; i < _polygonPoints.length; i++) {
//       _markers.add(
//         Marker(
//           markerId: MarkerId('point_$i'),
//           position: _polygonPoints[i],
//           icon: BitmapDescriptor.defaultMarkerWithHue(
//             BitmapDescriptor.hueAzure,
//           ),
//         ),
//       );
//     }

//     if (_polygonPoints.length >= 3) {
//       _polygons.add(
//         Polygon(
//           polygonId: const PolygonId('field_polygon'),
//           points: _polygonPoints,
//           strokeWidth: 2,
//           strokeColor: Colors.blue,
//           fillColor: Colors.blue.withOpacity(0.3),
//         ),
//       );
//     }

//     setState(() {});
//   }

//   void _clearPolygon() {
//     _polygonPoints.clear();
//     _polygons.clear();
//     _markers.clear();
//     _isConfirmEnabled = false;
//     setState(() {});
//   }

//   void _showFieldNameDialog() {
//     showDialog(
//       context: context,
//       builder: (_) => AlertDialog(
//         title: Text(AppLocalizations.of(context)!.enterFieldName),
//         content: TextField(
//           controller: _fieldNameController,
//           decoration: InputDecoration(
//             hintText: AppLocalizations.of(context)!.enterFieldNameHint,
//             border: const OutlineInputBorder(),
//           ),
//         ),
//         actions: [
//           TextButton(
//             onPressed: () => Navigator.pop(context),
//             child: Text(AppLocalizations.of(context)!.cancel),
//           ),
//           ElevatedButton(
//             onPressed: _isSaving ? null : _saveField,
//             child: _isSaving
//                 ? const SizedBox(
//                     width: 20,
//                     height: 20,
//                     child: CircularProgressIndicator(strokeWidth: 2),
//                   )
//                 : Text(AppLocalizations.of(context)!.save),
//           ),
//         ],
//       ),
//     );
//   }

//   Future<void> _saveField() async {
//     final fieldName = _fieldNameController.text.trim();
//     final prefs = await SharedPreferences.getInstance();
//     final userId = prefs.getString('userId');

//     if (userId == null) {
//       ScaffoldMessenger.of(context).showSnackBar(
//         SnackBar(content: Text(AppLocalizations.of(context)!.userIdNotFound)),
//       );
//       return;
//     }

//     if (fieldName.isEmpty || _polygonPoints.length < 3) {
//       ScaffoldMessenger.of(context).showSnackBar(
//         SnackBar(content: Text(AppLocalizations.of(context)!.invalidFieldData)),
//       );
//       return;
//     }

//     setState(() => _isSaving = true);

//     try {
//       final coordinates =
//           _polygonPoints.map((pt) => [pt.latitude, pt.longitude]).toList();
//       final geoJson = {
//         "type": "Polygon",
//         "coordinates": [coordinates],
//       };

//       await _supabase.from('user_fields').insert({
//         'user_id': userId,
//         'field_name': fieldName,
//         'coordinates': coordinates,
//         'geometry': geoJson,
//       });

//       ScaffoldMessenger.of(context).showSnackBar(
//         SnackBar(
//           content: Text(AppLocalizations.of(context)!.fieldSavedSuccess(fieldName)),
//         ),
//       );

//       _clearPolygon();
//       _fieldNameController.clear();
//       if (mounted) {
//         Navigator.pop(context); // close dialog
//         Navigator.pop(context, true); // return success
//       }
//     } catch (e) {
//       ScaffoldMessenger.of(context).showSnackBar(
//         SnackBar(content: Text(AppLocalizations.of(context)!.error(e.toString()))),
//       );
//     } finally {
//       if (mounted) setState(() => _isSaving = false);
//     }
//   }

//   @override
//   Widget build(BuildContext context) {
//     return Scaffold(
//       appBar: AppBar(
//         title: Text(AppLocalizations.of(context)!.addNewField),
//         backgroundColor: const Color(0xFF1B413C),
//       ),
//       body: _currentLocation == null
//           ? const Center(child: CircularProgressIndicator())
//           : Column(
//               children: [
//                 Expanded(
//                   child: Stack(
//                     children: [
//                       GoogleMap(
//                         initialCameraPosition: CameraPosition(
//                           target: _currentLocation!,
//                           zoom: 15,
//                         ),
//                         onMapCreated: (controller) {
//                           _mapController = controller;
//                         },
//                         myLocationEnabled: true,
//                         myLocationButtonEnabled: true,
//                         onTap: _onMapTap,
//                         polygons: _polygons,
//                         markers: _markers,
//                         mapType: MapType.hybrid,
//                       ),
//                       Positioned(
//                         top: 10,
//                         left: 15,
//                         right: 15,
//                         child: Material(
//                           elevation: 6,
//                           borderRadius: BorderRadius.circular(8),
//                           child: TextField(
//                             controller: _searchController,
//                             onSubmitted: _searchAndNavigate,
//                             decoration: InputDecoration(
//                               hintText: AppLocalizations.of(context)!.searchLocation,
//                               prefixIcon: const Icon(Icons.search),
//                               suffixIcon: IconButton(
//                                 icon: const Icon(Icons.clear),
//                                 onPressed: () => _searchController.clear(),
//                               ),
//                               border: OutlineInputBorder(
//                                 borderRadius: BorderRadius.circular(8),
//                               ),
//                               filled: true,
//                               fillColor: Colors.white,
//                             ),
//                           ),
//                         ),
//                       ),
//                       Positioned(
//                         bottom: 20,
//                         left: 20,
//                         child: Column(
//                           children: [
//                             FloatingActionButton(
//                               onPressed: _clearPolygon,
//                               tooltip: AppLocalizations.of(context)!.clearField,
//                               child: const Icon(Icons.clear),
//                             ),
//                             const SizedBox(height: 8),
//                             Text(
//                               AppLocalizations.of(context)!.clear,
//                               style: const TextStyle(color: Colors.black),
//                             ),
//                           ],
//                         ),
//                       ),
//                     ],
//                   ),
//                 ),
//                 Padding(
//                   padding: const EdgeInsets.all(16),
//                   child: SizedBox(
//                     width: double.infinity,
//                     child: ElevatedButton(
//                       onPressed: _isConfirmEnabled ? _showFieldNameDialog : null,
//                       style: ElevatedButton.styleFrom(
//                         backgroundColor: Colors.white,
//                         foregroundColor: const Color(0xFF116A2A),
//                         padding: const EdgeInsets.symmetric(vertical: 16),
//                         shape: RoundedRectangleBorder(
//                           borderRadius: BorderRadius.circular(8),
//                         ),
//                       ),
//                       child: Text(
//                         AppLocalizations.of(context)!.confirm,
//                         style: const TextStyle(
//                           fontSize: 16,
//                           fontWeight: FontWeight.bold,
//                         ),
//                       ),
//                     ),
//                   ),
//                 ),
//               ],
//             ),
//     );
//   }

//   @override
//   void dispose() {
//     _mapController.dispose();
//     _fieldNameController.dispose();
//     _searchController.dispose();
//     super.dispose();
//   }
// }



import 'dart:math';  // For area calculation math

import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:geolocator/geolocator.dart';
import 'package:geocoding/geocoding.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:farmmatrix/l10n/app_localizations.dart';

class AddFieldScreen extends StatefulWidget {
  const AddFieldScreen({super.key});

  @override
  _AddFieldScreenState createState() => _AddFieldScreenState();
}

class _AddFieldScreenState extends State<AddFieldScreen> {
  late GoogleMapController _mapController;
  LatLng? _currentLocation;
  final Set<Polygon> _polygons = {};
  final Set<Marker> _markers = {};
  final List<LatLng> _polygonPoints = [];
  final TextEditingController _fieldNameController = TextEditingController();
  final TextEditingController _searchController = TextEditingController();
  final SupabaseClient _supabase = Supabase.instance.client;
  bool _isSaving = false;
  bool _isConfirmEnabled = false;

  @override
  void initState() {
    super.initState();
    _getCurrentLocation();
  }

  Future<void> _getCurrentLocation() async {
    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        throw Exception(AppLocalizations.of(context)!.locationServicesDisabled);
      }

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) {
          throw Exception(AppLocalizations.of(context)!.locationPermissionsDenied);
        }
      }

      Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );
      setState(() {
        _currentLocation = LatLng(position.latitude, position.longitude);
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.error(e.toString()))),
      );
    }
  }

  Future<void> _searchAndNavigate(String query) async {
    try {
      List<Location> locations = await locationFromAddress(query);
      if (locations.isNotEmpty) {
        final target = LatLng(
          locations.first.latitude,
          locations.first.longitude,
        );
        _mapController.animateCamera(CameraUpdate.newLatLngZoom(target, 16));
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(AppLocalizations.of(context)!.locationNotFound)),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.searchError(e.toString()))),
      );
    }
  }

  void _onMapTap(LatLng position) {
    _polygonPoints.add(position);
    _isConfirmEnabled = _polygonPoints.length >= 3;
    _updatePolygon();
  }

  void _updatePolygon() {
    _polygons.clear();
    _markers.clear();

    for (int i = 0; i < _polygonPoints.length; i++) {
      _markers.add(
        Marker(
          markerId: MarkerId('point_$i'),
          position: _polygonPoints[i],
          icon: BitmapDescriptor.defaultMarkerWithHue(
            BitmapDescriptor.hueAzure,
          ),
        ),
      );
    }

    if (_polygonPoints.length >= 3) {
      _polygons.add(
        Polygon(
          polygonId: const PolygonId('field_polygon'),
          points: _polygonPoints,
          strokeWidth: 2,
          strokeColor: Colors.blue,
          fillColor: Colors.blue.withOpacity(0.3),
        ),
      );
    }

    setState(() {});
  }

  void _clearPolygon() {
    _polygonPoints.clear();
    _polygons.clear();
    _markers.clear();
    _isConfirmEnabled = false;
    setState(() {});
  }

  void _showFieldNameDialog() {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(AppLocalizations.of(context)!.enterFieldName),
        content: TextField(
          controller: _fieldNameController,
          decoration: InputDecoration(
            hintText: AppLocalizations.of(context)!.enterFieldNameHint,
            border: const OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(AppLocalizations.of(context)!.cancel),
          ),
          ElevatedButton(
            onPressed: _isSaving ? null : _saveField,
            child: _isSaving
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(AppLocalizations.of(context)!.save),
          ),
        ],
      ),
    );
  }

  /// Calculates polygon area in acres using spherical shoelace formula
  /// (accurate for geographic coordinates)
  double _calculateAreaInAcres(List<LatLng> points) {
    if (points.length < 3) return 0.0;

    const double earthRadius = 6371009; // meters
    double area = 0.0;

    for (int i = 0; i < points.length; i++) {
      final j = (i + 1) % points.length;

      final p1 = points[i];
      final p2 = points[j];

      final lat1 = p1.latitude * pi / 180;
      final lng1 = p1.longitude * pi / 180;
      final lat2 = p2.latitude * pi / 180;
      final lng2 = p2.longitude * pi / 180;

      area += (lng2 - lng1) * (2 + sin(lat1) + sin(lat2));
    }

    area = area.abs() * earthRadius * earthRadius / 2;

    const double sqmToAcres = 1 / 4046.86; // conversion factor
    return area * sqmToAcres;
  }

  Future<void> _saveField() async {
    final fieldName = _fieldNameController.text.trim();
    final prefs = await SharedPreferences.getInstance();
    final userId = prefs.getString('userId');

    if (userId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.userIdNotFound)),
      );
      return;
    }

    if (fieldName.isEmpty || _polygonPoints.length < 3) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.invalidFieldData)),
      );
      return;
    }

    setState(() => _isSaving = true);

    try {
      // Calculate area
      final areaInAcres = _calculateAreaInAcres(_polygonPoints);

      // Prepare coordinates and GeoJSON
      final coordinates =
          _polygonPoints.map((pt) => [pt.latitude, pt.longitude]).toList();
      final geoJson = {
        "type": "Polygon",
        "coordinates": [coordinates],
      };

      // Insert with area_in_acres
      await _supabase.from('user_fields').insert({
        'user_id': userId,
        'field_name': fieldName,
        'coordinates': coordinates,
        'geometry': geoJson,
        'area_in_acres': areaInAcres,  // New field
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppLocalizations.of(context)!.fieldSavedSuccess(fieldName)),
        ),
      );

      _clearPolygon();
      _fieldNameController.clear();
      if (mounted) {
        Navigator.pop(context); // close dialog
        Navigator.pop(context, true); // return success
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.error(e.toString()))),
      );
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(AppLocalizations.of(context)!.addNewField),
        backgroundColor: const Color(0xFF1B413C),
      ),
      body: _currentLocation == null
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                Expanded(
                  child: Stack(
                    children: [
                      GoogleMap(
                        initialCameraPosition: CameraPosition(
                          target: _currentLocation!,
                          zoom: 15,
                        ),
                        onMapCreated: (controller) {
                          _mapController = controller;
                        },
                        myLocationEnabled: true,
                        myLocationButtonEnabled: true,
                        onTap: _onMapTap,
                        polygons: _polygons,
                        markers: _markers,
                        mapType: MapType.hybrid,
                      ),
                      Positioned(
                        top: 10,
                        left: 15,
                        right: 15,
                        child: Material(
                          elevation: 6,
                          borderRadius: BorderRadius.circular(8),
                          child: TextField(
                            controller: _searchController,
                            onSubmitted: _searchAndNavigate,
                            decoration: InputDecoration(
                              hintText: AppLocalizations.of(context)!.searchLocation,
                              prefixIcon: const Icon(Icons.search),
                              suffixIcon: IconButton(
                                icon: const Icon(Icons.clear),
                                onPressed: () => _searchController.clear(),
                              ),
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(8),
                              ),
                              filled: true,
                              fillColor: Colors.white,
                            ),
                          ),
                        ),
                      ),
                      Positioned(
                        bottom: 20,
                        left: 20,
                        child: Column(
                          children: [
                            FloatingActionButton(
                              onPressed: _clearPolygon,
                              tooltip: AppLocalizations.of(context)!.clearField,
                              child: const Icon(Icons.clear),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              AppLocalizations.of(context)!.clear,
                              style: const TextStyle(color: Colors.black),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: _isConfirmEnabled ? _showFieldNameDialog : null,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: const Color(0xFF116A2A),
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                      child: Text(
                        AppLocalizations.of(context)!.confirm,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
    );
  }

  @override
  void dispose() {
    _mapController.dispose();
    _fieldNameController.dispose();
    _searchController.dispose();
    super.dispose();
  }
}