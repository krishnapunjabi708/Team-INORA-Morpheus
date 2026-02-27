import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:farmmatrix/services/field_services.dart';
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
  Set<Polygon> _polygons = {};
  String? _tileUrlTemplate;
  TileOverlayId? _currentOverlayId;

  bool _isLoading = true;
  String? _error;
  LatLngBounds? _fieldBounds;

  List<List<double>> _apiCoords = [];

  String _selectedParameter = "Fertility Index (Default)";
  bool _showFilters = false;

  late AppLocalizations loc;

  final List<String> _parameters = [
    "Fertility Index (Default)",
    "Nitrogen (N)",
    "Phosphorus (P)",
    "Potassium (K)",
    "Organic Carbon (OC)",
    "Electrical Conductivity (EC)",
    "Calcium (Ca)",
    "Magnesium (Mg)",
    "Sulphur (S)",
    "Soil pH",
  ];

  @override
  void initState() {
    super.initState();
    _getCurrentLocation();
  }

  Future<void> _getCurrentLocation() async {
    try {
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        throw Exception(loc.locationServicesDisabled);
      }

      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) {
          throw Exception(loc.locationPermissionsDenied);
        }
      }

      Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );

      setState(() {
        _currentLocation = LatLng(position.latitude, position.longitude);
      });

      await _loadFieldAndMapping();
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _loadFieldAndMapping() async {
    loc = AppLocalizations.of(context)!;

    try {
      final fieldInfo = await _fieldService.getFieldData(widget.fieldId);

      if (fieldInfo == null || fieldInfo.geometry == null) {
        throw Exception(loc.fieldMissing);
      }

      final coordinates = fieldInfo.geometry!['coordinates'][0];

      final points = <LatLng>[];

      double minLat = double.infinity, maxLat = -double.infinity;
      double minLng = double.infinity, maxLng = -double.infinity;

      _apiCoords.clear();

      for (var item in coordinates) {
        final lat = (item[0] as num).toDouble();
        final lng = (item[1] as num).toDouble();

        points.add(LatLng(lat, lng));
        _apiCoords.add([lng, lat]);

        minLat = lat < minLat ? lat : minLat;
        maxLat = lat > maxLat ? lat : maxLat;
        minLng = lng < minLng ? lng : minLng;
        maxLng = lng > maxLng ? lng : maxLng;
      }

      if (_apiCoords.first != _apiCoords.last) {
        _apiCoords.add(_apiCoords.first);
        points.add(points.first);
      }

      _polygons = {
        Polygon(
          polygonId: const PolygonId("field"),
          points: points,
          strokeWidth: 2,
          strokeColor: Colors.blue,
          fillColor: Colors.blue.withOpacity(0.2),
        ),
      };

      _fieldBounds = LatLngBounds(
        southwest: LatLng(minLat, minLng),
        northeast: LatLng(maxLat, maxLng),
      );

      await _fetchMapping();

      setState(() => _isLoading = false);

      if (_mapController != null && _fieldBounds != null) {
        _mapController!.animateCamera(
          CameraUpdate.newLatLngBounds(_fieldBounds!, 50),
        );
      }
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _fetchMapping() async {
    final apiUrl = dotenv.env['FERTILITY_MAPPING_API'];

    if (apiUrl == null || apiUrl.isEmpty) {
      throw Exception("FERTILITY_MAPPING_API not found in .env");
    }

    final payload = {
      "coordinates": _apiCoords,
      "parameter": _selectedParameter,
    };

    try {
      final response = await http.post(
        Uri.parse(apiUrl),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode(payload),
      );

      if (response.statusCode != 200) {
        throw Exception("${loc.apiError} ${response.statusCode}");
      }

      final body = jsonDecode(response.body);

      setState(() {
        _tileUrlTemplate = body["tile_url"];
        _currentOverlayId = TileOverlayId(
          "overlay_${DateTime.now().millisecondsSinceEpoch}",
        );
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
      });
    }
  }

  Future<void> _reloadWithParameter(String parameter) async {
    setState(() {
      _selectedParameter = parameter;
      _showFilters = false;
      _isLoading = true;
      _tileUrlTemplate = null;
      _currentOverlayId = null;
    });

    await Future.delayed(const Duration(milliseconds: 200));
    await _fetchMapping();
    setState(() => _isLoading = false);
  }

  void _clearOverlay() {
    setState(() {
      _tileUrlTemplate = null;
      _currentOverlayId = null;
      _selectedParameter = "Fertility Index (Default)";
    });
  }

  @override
  Widget build(BuildContext context) {
    loc = AppLocalizations.of(context)!;

    if (_error != null) {
      return Scaffold(
        appBar: AppBar(
          title: Text(loc.fertilityMapping),
          backgroundColor: const Color(0xFF1B413C),
        ),
        body: Center(child: Text(_error!)),
      );
    }

    if (_currentLocation == null) {
      return Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.fertilityMapping),
        backgroundColor: const Color(0xFF1B413C),
      ),
      body: Column(
        children: [
          _buildFilterBar(),
          Expanded(
            child: Stack(
              children: [
                GoogleMap(
                  mapType: MapType.hybrid,
                  initialCameraPosition: CameraPosition(
                    target: _currentLocation!,
                    zoom: 15,
                  ),
                  myLocationEnabled: true,
                  polygons: _polygons,
                  tileOverlays:
                      (_tileUrlTemplate != null && _currentOverlayId != null)
                          ? {
                            TileOverlay(
                              tileOverlayId: _currentOverlayId!,
                              tileProvider: FertilityTileProvider(
                                urlTemplate: _tileUrlTemplate!,
                              ),
                              transparency: 0.45,
                            ),
                          }
                          : {},
                  onMapCreated: (controller) {
                    _mapController = controller;
                  },
                ),
                if (_isLoading)
                  const Center(child: CircularProgressIndicator()),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1B413C),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 8,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(30),
                    ),
                  ),
                  onPressed: () {
                    setState(() => _showFilters = !_showFilters);
                  },
                  icon: const Icon(Icons.tune, size: 18),
                  label: Text(
                    loc.filterByNutrients,
                    style: const TextStyle(fontSize: 14),
                  ),
                ),
                const SizedBox(width: 12),
                if (_tileUrlTemplate != null)
                  _buildSelectedPill(_selectedParameter),
              ],
            ),
          ),
          const SizedBox(height: 12),
          if (_showFilters)
            SizedBox(
              height: 36,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: _parameters.length,
                separatorBuilder: (_, __) => const SizedBox(width: 10),
                itemBuilder: (context, index) {
                  final param = _parameters[index];
                  return GestureDetector(
                    onTap: () => _reloadWithParameter(param),
                    child: _buildFilterPill(param),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildFilterPill(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.grey.shade200,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Text(
        _getLocalizedParameter(text),
        style: const TextStyle(fontSize: 14),
      ),
    );
  }

  Widget _buildSelectedPill(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        border: Border.all(color: const Color(0xFF1B413C)),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          GestureDetector(
            onTap: _clearOverlay,
            child: const Icon(Icons.close, size: 16),
          ),
          const SizedBox(width: 8),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 180),
            child: Text(
              _getLocalizedParameter(text),
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 14),
            ),
          ),
        ],
      ),
    );
  }

  String _getLocalizedParameter(String param) {
    switch (param) {
      case "Fertility Index (Default)":
        return loc.fertilityIndexDefault;
      case "Nitrogen (N)":
        return loc.nitrogenN;
      case "Phosphorus (P)":
        return loc.phosphorusP;
      case "Potassium (K)":
        return loc.potassiumK;
      case "Organic Carbon (OC)":
        return loc.organicCarbonOC;
      case "Electrical Conductivity (EC)":
        return loc.electricalConductivityEC;
      case "Calcium (Ca)":
        return loc.calciumCa;
      case "Magnesium (Mg)":
        return loc.magnesiumMg;
      case "Sulphur (S)":
        return loc.sulphurS;
      case "Soil pH":
        return loc.soilPh;
      default:
        return param;
    }
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
    } catch (_) {
      return Tile(256, 256, Uint8List(0));
    }
  }
}
