import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:farmmatrix/services/field_services.dart';
import 'package:farmmatrix/screens/home/home_screen.dart';
import 'package:farmmatrix/config/app_config.dart';
import 'package:farmmatrix/l10n/app_localizations.dart';


class FieldMapScreen extends StatefulWidget {
  final String fieldId;

  const FieldMapScreen({super.key, required this.fieldId});

  @override
  State<FieldMapScreen> createState() => _FieldMapScreenState();
}

class _FieldMapScreenState extends State<FieldMapScreen> {
  final FieldService _fieldService = FieldService();
  GoogleMapController? _mapController;
  LatLng? _currentLocation;
  Set<Marker> _markers = {};
  Set<Polygon> _polygons = {};
  bool _isLoading = true;
  String? _error;
  LatLngBounds? _fieldBounds;

  static const LatLng _fallbackCenter = LatLng(18.5204, 73.8567); // Pune, India

  @override
  void initState() {
    super.initState();
    _initializeMap();
  }

  Future<void> _initializeMap() async {
    setState(() {
      _isLoading = true;
    });

    // Get current location
    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        setState(() {
          _error = AppLocalizations.of(context)!.locationServicesDisabled;
          _isLoading = false;
        });
        return;
      }

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) {
          setState(() {
            _error = AppLocalizations.of(context)!.locationPermissionsDenied;
            _isLoading = false;
          });
          return;
        }
      }

      Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );
      setState(() {
        _currentLocation = LatLng(position.latitude, position.longitude);
      });
    } catch (e) {
      setState(() {
        _error = AppLocalizations.of(context)!.errorGettingLocation(e.toString());
        _isLoading = false;
      });
      return;
    }

    // Fetch field data
    await _loadFieldData();
  }

  Future<void> _loadFieldData() async {
    try {
      // Fetch field data from Supabase
      final fieldInfo = await _fieldService.getFieldData(widget.fieldId);
      if (fieldInfo == null || fieldInfo.geometry == null) {
        throw Exception(AppLocalizations.of(context)!.fieldDataMissing);
      }

      // Extract coordinates from GeoJSON
      final coordinates = fieldInfo.geometry!['coordinates'];
      if (coordinates is! List || coordinates.isEmpty || coordinates[0] is! List) {
        throw Exception(AppLocalizations.of(context)!.invalidGeometry);
      }
      final coordsList = List<List<dynamic>>.from(coordinates[0]);

      final points = <LatLng>[];
      double minLat = double.infinity, maxLat = -double.infinity;
      double minLng = double.infinity, maxLng = -double.infinity;

      for (var item in coordsList) {
        if (item.length < 2) continue;
        final lat = (item[0] as num?)?.toDouble(); // Assume first is latitude
        final lng = (item[1] as num?)?.toDouble(); // Assume second is longitude
        if (lat == null || lng == null) continue;

        points.add(LatLng(lat, lng));

        // Update bounds
        minLat = lat < minLat ? lat : minLat;
        maxLat = lat > maxLat ? lat : maxLat;
        minLng = lng < minLng ? lng : minLng;
        maxLng = lng > maxLng ? lng : maxLng;
      }

      // Close the polygon if needed
      if (points.isNotEmpty && points.first != points.last) {
        points.add(points.first);
      }

      // Create markers
      final markers = <Marker>{};
      for (var i = 0; i < points.length; i++) {
        markers.add(
          Marker(
            markerId: MarkerId('point_$i'),
            position: points[i],
            icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueAzure),
          ),
        );
      }

      // Create polygon
      final polygons = {
        Polygon(
          polygonId: const PolygonId('field_polygon'),
          points: points,
          strokeWidth: 2,
          strokeColor: Colors.blue,
          fillColor: Colors.blue.withOpacity(0.2),
        ),
      };

      // Set bounds for zooming
      final bounds = points.isNotEmpty
          ? LatLngBounds(
              southwest: LatLng(minLat, minLng),
              northeast: LatLng(maxLat, maxLng),
            )
          : null;

      setState(() {
        _markers = markers;
        _polygons = polygons;
        _fieldBounds = bounds;
        _isLoading = false;
      });

      // Zoom to field bounds
      if (_mapController != null && _fieldBounds != null) {
        await _mapController!.animateCamera(
          CameraUpdate.newLatLngBounds(_fieldBounds!, 50),
        );
      }
    } catch (e) {
      setState(() {
        _error = AppLocalizations.of(context)!.errorLoadingData(e.toString());
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      return Scaffold(
        appBar: AppBar(
          title: Text(
            AppLocalizations.of(context)!.yourSelectedField,
            style: TextStyle(
              fontFamily: AppConfig.fontFamily,
              color: Colors.white,
            ),
          ),
          backgroundColor: const Color(0xFF178D38),
          leading: IconButton(
            icon: const Icon(Icons.arrow_back, color: Colors.white),
            onPressed: () {
              Navigator.of(context).pushReplacement(
                MaterialPageRoute(builder: (context) => const HomeScreen()),
              );
            },
          ),
          automaticallyImplyLeading: false,
        ),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                AppLocalizations.of(context)!.error(_error!),
                style: TextStyle(
                  fontFamily: AppConfig.fontFamily,
                  fontSize: 16,
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () {
                  setState(() {
                    _error = null;
                    _isLoading = true;
                  });
                  _initializeMap();
                },
                child: Text(
                  AppLocalizations.of(context)!.retry,
                  style: TextStyle(
                    fontFamily: AppConfig.fontFamily,
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(
          AppLocalizations.of(context)!.yourSelectedField,
          style: TextStyle(
            fontFamily: AppConfig.fontFamily,
            color: Colors.white,
          ),
        ),
        backgroundColor: const Color(0xFF178D38),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () {
            Navigator.of(context).pushReplacement(
              MaterialPageRoute(builder: (context) => const HomeScreen()),
            );
          },
        ),
        automaticallyImplyLeading: false,
      ),
      body: Stack(
        children: [
          GoogleMap(
            mapType: MapType.hybrid,
            initialCameraPosition: CameraPosition(
              target: _currentLocation ?? _fallbackCenter,
              zoom: 15,
            ),
            polygons: _polygons,
            markers: _markers,
            onMapCreated: (GoogleMapController controller) {
              _mapController = controller;
              if (_fieldBounds != null) {
                controller.animateCamera(
                  CameraUpdate.newLatLngBounds(_fieldBounds!, 50),
                );
              }
            },
          ),
          if (_isLoading)
            Center(
              child: Card(
                color: Colors.black54,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const CircularProgressIndicator(color: Colors.white),
                      const SizedBox(height: 8),
                      Text(
                        AppLocalizations.of(context)!.loadingFieldMap,
                        style: TextStyle(
                          fontFamily: AppConfig.fontFamily,
                          color: Colors.white,
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

  @override
  void dispose() {
    _mapController?.dispose();
    super.dispose();
  }
}