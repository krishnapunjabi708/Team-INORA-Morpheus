import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart'
    show
        BitmapDescriptor,
        CameraPosition,
        CameraUpdate,
        GoogleMap,
        GoogleMapController,
        LatLng,
        LatLngBounds,
        MapType,
        Marker,
        MarkerId,
        Polygon,
        PolygonId,
        Tile,
        TileOverlay,
        TileOverlayId,
        TileProvider;
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:farmmatrix/models/field_info_model.dart';
import 'package:farmmatrix/services/field_services.dart';
import 'package:farmmatrix/screens/home/home_screen.dart';
import 'package:farmmatrix/l10n/app_localizations.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

class SatelliteMappingScreen extends StatefulWidget {
  final String fieldId;

  const SatelliteMappingScreen({super.key, required this.fieldId});

  @override
  State<SatelliteMappingScreen> createState() => _SatelliteMappingScreenState();
}

class _SatelliteMappingScreenState extends State<SatelliteMappingScreen> {
  final FieldService _fieldService = FieldService();
  GoogleMapController? _mapController;
  LatLng? _currentLocation;
  Set<Marker> _markers = {};
  Set<Polygon> _polygons = {};
  String? _tileUrlTemplate;
  String? _startDate;
  String? _endDate;
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
        debugPrint(
          'Current location: ${position.latitude}, ${position.longitude}',
        );
      });
    } catch (e) {
      setState(() {
        _error = AppLocalizations.of(
          context,
        )!.errorGettingLocation(e.toString());
        _isLoading = false;
      });
      return;
    }

    // Fetch field data and API data
    await _loadFieldAndFertilityData();
  }

  Future<void> _loadFieldAndFertilityData() async {
    try {
      // Fetch field data from Supabase
      final fieldInfo = await _fieldService.getFieldData(widget.fieldId);
      if (fieldInfo == null || fieldInfo.geometry == null) {
        throw Exception(AppLocalizations.of(context)!.fieldDataMissing);
      }

      // Log raw geometry
      debugPrint('Raw geometry: ${jsonEncode(fieldInfo.geometry)}');

      // Extract coordinates from GeoJSON
      final coordinates = fieldInfo.geometry!['coordinates'];
      if (coordinates is! List ||
          coordinates.isEmpty ||
          coordinates[0] is! List) {
        throw Exception(AppLocalizations.of(context)!.invalidGeometry);
      }
      final coordsList = List<List<dynamic>>.from(coordinates[0]);

      // Log coordinates
      debugPrint('Parsed coordinates: $coordsList');

      final apiCoords = <List<double>>[];
      final points = <LatLng>[];
      double minLat = double.infinity, maxLat = -double.infinity;
      double minLng = double.infinity, maxLng = -double.infinity;

      for (var item in coordsList) {
        if (item.length < 2) continue;
        final lat = (item[0] as num?)?.toDouble(); // Assume first is latitude
        final lng = (item[1] as num?)?.toDouble(); // Assume second is longitude
        if (lat == null || lng == null) continue;

        // API expects [longitude, latitude]
        apiCoords.add([lng, lat]);
        // Google Maps expects LatLng(latitude, longitude)
        points.add(LatLng(lat, lng));

        // Update bounds
        minLat = lat < minLat ? lat : minLat;
        maxLat = lat > maxLat ? lat : maxLat;
        minLng = lng < minLng ? lng : minLng;
        maxLng = lng > maxLng ? lng : maxLng;
      }

      // Log plotted points
      debugPrint(
        'Plotted points: ${points.map((p) => [p.latitude, p.longitude]).toList()}',
      );

      // Close the polygon if needed
      if (apiCoords.isNotEmpty && apiCoords.first != apiCoords.last) {
        apiCoords.add(apiCoords.first);
        points.add(points.first);
      }

      // Create markers
      final markers = <Marker>{};
      for (var i = 0; i < points.length; i++) {
        markers.add(
          Marker(
            markerId: MarkerId('point_$i'),
            position: points[i],
            icon: BitmapDescriptor.defaultMarkerWithHue(
              BitmapDescriptor.hueAzure,
            ),
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
      final bounds =
          points.isNotEmpty
              ? LatLngBounds(
                southwest: LatLng(minLat, minLng),
                northeast: LatLng(maxLat, maxLng),
              )
              : null;

      // Log bounds
      if (bounds != null) {
        debugPrint(
          'Map bounds: SW(${bounds.southwest.latitude}, ${bounds.southwest.longitude}), NE(${bounds.northeast.latitude}, ${bounds.northeast.longitude})',
        );
      }

      setState(() {
        _markers = markers;
        _polygons = polygons;
        _fieldBounds = bounds;
      });

      // Fetch fertility data from API
      final baseUrl = dotenv.env['FERTILITY_API_BASE_URL'];

      if (baseUrl == null || baseUrl.isEmpty) {
        throw Exception("API URL not found");
      }

      final apiUrl = "$baseUrl/fertility";
      final payload = {'coordinates': apiCoords};

      // Log API input
      const encoder = JsonEncoder.withIndent('  ');
      debugPrint('API Request Payload:\n${encoder.convert(payload)}');

      final response = await http.post(
        Uri.parse(apiUrl),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(payload),
      );

      // Log API output
      if (response.statusCode == 200) {
        try {
          final body = jsonDecode(response.body);
          debugPrint('API Response (Success):\n${encoder.convert(body)}');
        } catch (e) {
          debugPrint('API Response (Success, Raw):\n${response.body}');
        }
      } else {
        debugPrint(
          'API Response (Error):\nStatus Code: ${response.statusCode}\nBody: ${response.body}',
        );
        throw Exception(
          AppLocalizations.of(
            context,
          )!.apiRequestFailed(response.statusCode.toString()),
        );
      }

      final body = jsonDecode(response.body) as Map<String, dynamic>;
      setState(() {
        _tileUrlTemplate = body['tile_url'] as String?;
        _startDate = body['start_date'] as String?;
        _endDate = body['end_date'] as String?;
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
          backgroundColor: const Color(0xFF178D38),
          title: Text(AppLocalizations.of(context)!.fertilityMapping),
          leading: IconButton(
            icon: const Icon(Icons.arrow_back, color: Colors.white),
            onPressed: () {
              Navigator.of(context).pushReplacement(
                MaterialPageRoute(builder: (context) => const HomeScreen()),
              );
            },
          ),
        ),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(AppLocalizations.of(context)!.error(_error!)),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () {
                  setState(() {
                    _error = null;
                    _isLoading = true;
                  });
                  _initializeMap();
                },
                child: Text(AppLocalizations.of(context)!.retry),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF1B413C),
        title: Text(AppLocalizations.of(context)!.fertilityMapping),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
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
            tileOverlays:
                _tileUrlTemplate != null
                    ? {
                      TileOverlay(
                        tileOverlayId: const TileOverlayId('fertility'),
                        tileProvider: FertilityTileProvider(
                          urlTemplate: _tileUrlTemplate!,
                        ),
                        transparency: 0.45,
                      ),
                    }
                    : {},
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
                        AppLocalizations.of(context)!.loadingFertilityMap,
                        style: const TextStyle(color: Colors.white),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          if (!_isLoading && _startDate != null && _endDate != null)
            Positioned(
              bottom: 27,
              left: 16,
              right: 60,
              child: Card(
                color: Colors.white.withOpacity(0.9),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        AppLocalizations.of(
                          context,
                        )!.fertilityMapPeriod(_startDate!, _endDate!),
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        children: [
                          _LegendItem(
                            color: Colors.red,
                            label: AppLocalizations.of(context)!.fertilityLow,
                          ),
                          _LegendItem(
                            color: Colors.yellow,
                            label:
                                AppLocalizations.of(context)!.fertilityModerate,
                          ),
                          _LegendItem(
                            color: Colors.green,
                            label: AppLocalizations.of(context)!.fertilityHigh,
                          ),
                        ],
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

class _LegendItem extends StatelessWidget {
  final Color color;
  final String label;

  const _LegendItem({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 16,
          height: 16,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 14)),
      ],
    );
  }
}

class FertilityTileProvider implements TileProvider {
  final String urlTemplate;

  const FertilityTileProvider({required this.urlTemplate});

  @override
  Future<Tile> getTile(int x, int y, int? zoom) async {
    final z = zoom ?? 0;
    final url = urlTemplate
        .replaceAll('{x}', x.toString())
        .replaceAll('{y}', y.toString())
        .replaceAll('{z}', z.toString());

    try {
      final response = await http.get(Uri.parse(url));
      if (response.statusCode != 200 || response.bodyBytes.isEmpty) {
        return Tile(256, 256, Uint8List(0));
      }

      return Tile(256, 256, response.bodyBytes);
    } catch (e) {
      debugPrint('Error loading tile: $e');
      return Tile(256, 256, Uint8List(0));
    }
  }
}
