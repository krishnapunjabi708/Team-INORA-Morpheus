import 'package:flutter/material.dart';
import 'package:farmmatrix/config/app_config.dart';
import 'package:farmmatrix/screens/home/home_screen.dart';
import 'package:farmmatrix/screens/profile/profile_screen.dart';
import 'package:farmmatrix/models/field_info_model.dart';
import 'package:farmmatrix/services/field_services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:math';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:farmmatrix/l10n/app_localizations.dart';

class DashboardScreen extends StatefulWidget {
  final FieldInfoModel? selectedField;

  const DashboardScreen({super.key, this.selectedField});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _selectedIndex = 1;
  bool _isLoading = true;
  FieldInfoModel? _fieldData;
  FieldInfoModel? _selectedField;
  final FieldService _fieldService = FieldService();

  // Variables to store API data
  double soilPhValue = 0.0;
  String soilTextureValue = "";
  double soilSalinityValue = 0.0;
  double organicCarbonValue = 0.0;
  double nutrientsHoldingValue = 0.0;
  double landSurfaceTempValue = 0.0;
  double ndwiValue = 0.0;

  @override
  void initState() {
    super.initState();
    _initializeFieldData();
  }

  Future<void> _initializeFieldData() async {
    setState(() {
      _isLoading = true;
    });

    if (widget.selectedField != null) {
      _selectedField = widget.selectedField;
    } else {
      final prefs = await SharedPreferences.getInstance();
      final fieldJson = prefs.getString('selectedField');
      if (fieldJson != null) {
        try {
          final fieldMap = jsonDecode(fieldJson) as Map<String, dynamic>;
          _selectedField = FieldInfoModel.fromMap(fieldMap);
        } catch (e) {
          print('Error decoding saved field: $e');
        }
      }
    }

    await _fetchFieldData();
  }

  Future<void> _fetchFieldData() async {
    if (_selectedField == null) {
      setState(() {
        _isLoading = false;
      });
      return;
    }

    try {
      final fieldData = await _fieldService.getFieldData(_selectedField!.id);
      print('Field Data from Supabase: $fieldData');
      setState(() {
        _fieldData = fieldData;
      });

      if (fieldData != null) {
        List<List<double>> coords = [];
        if (fieldData.geometry['type'] == 'Polygon') {
          final rawCoords =
              fieldData.geometry['coordinates']?[0] as List<dynamic>?;
          if (rawCoords != null && rawCoords.isNotEmpty) {
            coords =
                rawCoords.map((c) => [c[0] as double, c[1] as double]).toList();
          }
        } else if (fieldData.coordinates.isNotEmpty) {
          final rawCoords = fieldData.coordinates;
          if (rawCoords.isNotEmpty) {
            coords =
                rawCoords
                    .where((c) => c is List && c.length >= 2)
                    .map((c) => [c[0] as double, c[1] as double])
                    .toList();
          }
        }

        if (coords.isEmpty) {
          throw Exception(AppLocalizations.of(context)!.noCoordinatesAvailable);
        }

        double latSum = 0.0;
        double lonSum = 0.0;
        int count = coords.length;
        for (var coord in coords) {
          latSum += coord[0];
          lonSum += coord[1];
        }
        final lat = latSum / count;
        final lon = lonSum / count;
        print('Calculated centroid - Latitude: $lat, Longitude: $lon');

        Map<String, dynamic>? geometry;
        if (fieldData.geometry['type'] == 'Polygon') {
          final coordsList = coords.map((c) => [c[1], c[0]]).toList();
          if (coordsList.isNotEmpty && coordsList.first != coordsList.last) {
            coordsList.add(coordsList.first);
          }
          geometry = {
            'type': 'Polygon',
            'coordinates': [coordsList],
          };
          print('Prepared geometry for API: $geometry');
        }

        await _fetchSoilParameters(lat: lat, lon: lon, geometry: geometry);
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            AppLocalizations.of(context)!.errorFetchingFieldData(e.toString()),
          ),
        ),
      );
      print('Error in _fetchFieldData: $e');
    }
  }

  Future<Map<String, dynamic>> _fetchSoilParameters({
    required double lat,
    required double lon,
    Map<String, dynamic>? geometry,
  }) async {
    try {
      final baseUrl = dotenv.env['SOIL_ANALYZE_BASE_URL'];

      if (baseUrl == null || baseUrl.isEmpty) {
        throw Exception("API URL not found");
      }

      final url = Uri.parse("$baseUrl/analyze");
      final Map<String, dynamic> body = {
        'latitude': lat,
        'longitude': lon,
        'intercept': 5.0,
        'slope_clay': 20.0,
        'slope_om': 15.0,
      };

      if (geometry != null) {
        body['geometry'] = geometry;
      }

      print('API Request Body: ${json.encode(body)}');

      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: json.encode(body),
      );

      print('API Response Status Code: ${response.statusCode}');
      print('API Response Body: ${response.body}');

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() {
          soilPhValue = data['pH']?.toDouble() ?? 0.0;
          soilTextureValue =
              data['soil_texture'] ?? AppLocalizations.of(context)!.unknown;
          soilSalinityValue = data['salinity_ndsi']?.toDouble() ?? 0.0;
          organicCarbonValue = data['organic_carbon_pct']?.toDouble() ?? 0.0;
          nutrientsHoldingValue = data['cec_cmolckg']?.toDouble() ?? 0.0;
          landSurfaceTempValue = data['lst_celsius']?.toDouble() ?? 0.0;
          ndwiValue = data['ndwi']?.toDouble() ?? -0.2;
          _isLoading = false;
        });

        return data;
      } else {
        throw Exception(
          AppLocalizations.of(
            context,
          )!.errorFetchingData(response.statusCode.toString()),
        );
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            AppLocalizations.of(context)!.errorFetchingData(e.toString()),
          ),
        ),
      );
      print('Error in _fetchSoilParameters: $e');
      rethrow;
    }
  }

  Color _getPhColor(double value) {
    if (value >= 6.5 && value <= 7.5) return Colors.green;
    if ((value >= 5.5 && value < 6.5) || (value > 7.5 && value <= 8.0))
      return Colors.yellow;
    return Colors.red;
  }

  String _getPhStatus(double value) {
    if (value >= 6.5 && value <= 7.5)
      return AppLocalizations.of(context)!.phStatusIdeal;
    if ((value >= 5.5 && value < 6.5) || (value > 7.5 && value <= 8.0))
      return AppLocalizations.of(context)!.phStatusAcceptable;
    return AppLocalizations.of(context)!.phStatusPoor;
  }

  String _getPhTooltip(double value) {
    if (value >= 6.5 && value <= 7.5)
      return AppLocalizations.of(context)!.phTooltipIdeal;
    if ((value >= 5.5 && value < 6.5) || (value > 7.5 && value <= 8.0))
      return AppLocalizations.of(context)!.phTooltipMildlyAcidicAlkaline;
    return AppLocalizations.of(context)!.phTooltipCorrectionNeeded;
  }

  Color _getTextureColor(String texture) {
    final normalized = texture.toLowerCase();

    if (normalized == "loam") {
      return Colors.green;
    }

    if (normalized == "sandy loam" || normalized == "silty loam") {
      return Colors.yellow;
    }

    return Colors.red;
  }

  String _getLocalizedTexture(String texture) {
    final loc = AppLocalizations.of(context)!;
    final normalized = texture.toLowerCase();

    switch (normalized) {
      case "loam":
        return loc.textureLoam;
      case "sandy loam":
        return loc.textureSandyLoam;
      case "silty loam":
        return loc.textureSiltyLoam;
      case "clay loam": // ← add this line
        return loc
            .textureClayLoam; // make sure this key exists in your .arb file
      default:
        return loc.unknown;
    }
  }

  String _getTextureTooltip(String texture) {
    final loc = AppLocalizations.of(context)!;
    final normalized = texture.toLowerCase();

    if (normalized == "loam") {
      return loc.textureTooltipGood;
    }

    if (normalized == "sandy loam" || normalized == "silty loam") {
      return loc.textureTooltipWorkable;
    }

    return loc.textureTooltipOrganicMatter;
  }

  Color _getSalinityColor(double value) {
    if (value < 0.10) return Colors.green;
    if (value >= 0.10 && value <= 0.23) return Colors.green;
    if (value >= 0.23 && value <= 0.33) return Colors.yellow;
    if (value >= 0.33 && value <= 0.43)
      return const Color.fromARGB(255, 255, 190, 59);
    return Colors.red;
  }

  String _getSalinityStatus(double value) {
    if (value < 0.10)
      return AppLocalizations.of(context)!.salinityStatusVeryLow;
    if (value >= 0.10 && value <= 0.23)
      return AppLocalizations.of(context)!.salinityStatusLow;
    if (value >= 0.23 && value <= 0.33)
      return AppLocalizations.of(context)!.salinityStatusModerate;
    if (value >= 0.33 && value <= 0.43)
      return AppLocalizations.of(context)!.salinityStatusHigh;
    return AppLocalizations.of(context)!.salinityStatusVeryHigh;
  }

  String _getSalinityTooltip(double value) {
    if (value < 0.10)
      return AppLocalizations.of(context)!.salinityTooltipExcellent;
    if (value >= 0.10 && value <= 0.23)
      return AppLocalizations.of(context)!.salinityTooltipSuitable;
    if (value >= 0.23 && value <= 0.33)
      return AppLocalizations.of(context)!.salinityTooltipMonitor;
    if (value >= 0.33 && value <= 0.43)
      return AppLocalizations.of(context)!.salinityTooltipTreatment;
    return AppLocalizations.of(context)!.salinityTooltipPoor;
  }

  Color _getOrganicCarbonColor(double value) {
    if (value > 2.0) return Colors.green;
    if (value >= 1.0 && value <= 2.0) return Colors.yellow;
    return Colors.red;
  }

  String _getOrganicCarbonStatus(double value) {
    if (value > 2.0)
      return AppLocalizations.of(context)!.organicCarbonStatusRich;
    if (value >= 1.0 && value <= 2.0)
      return AppLocalizations.of(context)!.organicCarbonStatusModerate;
    if (value >= 0.0 && value <= 1.0)
      return AppLocalizations.of(context)!.organicCarbonStatusLow;
    return AppLocalizations.of(context)!.organicCarbonStatusWaterBody;
  }

  String _getOrganicCarbonTooltip(double value) {
    if (value > 2.0)
      return AppLocalizations.of(context)!.organicCarbonTooltipGood;
    if (value >= 1.0 && value <= 2.0)
      return AppLocalizations.of(context)!.organicCarbonTooltipCompost;
    return AppLocalizations.of(context)!.organicCarbonTooltipLow;
  }

  Color _getCECColor(double value) {
    if (value > 15) return Colors.green;
    if (value >= 10 && value <= 15) return Colors.yellow;
    return Colors.red;
  }

  String _getCECStatus(double value) {
    if (value > 15) return AppLocalizations.of(context)!.cecStatusHigh;
    if (value >= 10 && value <= 15)
      return AppLocalizations.of(context)!.cecStatusAverage;
    return AppLocalizations.of(context)!.cecStatusLow;
  }

  String _getCECTooltip(double value) {
    if (value > 15) return AppLocalizations.of(context)!.cecTooltipHigh;
    if (value >= 10 && value <= 15)
      return AppLocalizations.of(context)!.cecTooltipAverage;
    return AppLocalizations.of(context)!.cecTooltipLow;
  }

  Color _getLSTColor(double value) {
    if (value <= 20) return const Color.fromARGB(255, 42, 161, 101);
    if (value >= 20 && value <= 30) return Colors.green;
    if (value >= 30 && value <= 35) return Colors.yellow;
    if (value > 35 && value <= 40)
      return const Color.fromARGB(255, 229, 154, 34);
    return Colors.red;
  }

  String _getLSTStatus(double value) {
    if (value <= 20) return AppLocalizations.of(context)!.lstStatusCool;
    if (value >= 20 && value <= 30)
      return AppLocalizations.of(context)!.lstStatusOptimal;
    if (value >= 30 && value <= 35)
      return AppLocalizations.of(context)!.lstStatusModerate;
    if (value > 35 && value <= 40)
      return AppLocalizations.of(context)!.lstStatusHigh;
    return AppLocalizations.of(context)!.lstStatusExtreme;
  }

  String _getLSTTooltip(double value) {
    if (value <= 20) return AppLocalizations.of(context)!.lstTooltipCool;
    if (value >= 20 && value <= 30)
      return AppLocalizations.of(context)!.lstTooltipOptimal;
    if (value >= 30 && value <= 35)
      return AppLocalizations.of(context)!.lstTooltipModerate;
    if (value > 35 && value <= 40)
      return AppLocalizations.of(context)!.lstTooltipHigh;
    return AppLocalizations.of(context)!.lstTooltipExtreme;
  }

  Color _getWaterContentColor(double value) {
    if (value > 0.0) return Colors.blue;
    if (value >= -0.10) return Colors.green;
    if (value >= -0.20) return Colors.yellow;
    if (value >= -0.30) return Colors.orange;
    return Colors.red;
  }

  String _getWaterContentStatus(double value) {
    if (value > 0.0)
      return AppLocalizations.of(context)!.waterContentStatusWaterBody;
    if (value >= -0.10)
      return AppLocalizations.of(context)!.waterContentStatusAdequate;
    if (value >= -0.20)
      return AppLocalizations.of(context)!.waterContentStatusMild;
    if (value >= -0.30)
      return AppLocalizations.of(context)!.waterContentStatusModerate;
    return AppLocalizations.of(context)!.waterContentStatusDry;
  }

  String _getWaterContentTooltip(double value) {
    if (value > 0.0)
      return AppLocalizations.of(context)!.waterContentTooltipWaterBody;
    if (value >= -0.10)
      return AppLocalizations.of(context)!.waterContentTooltipAdequate;
    if (value >= -0.20)
      return AppLocalizations.of(context)!.waterContentTooltipMild;
    if (value >= -0.30)
      return AppLocalizations.of(context)!.waterContentTooltipModerate;
    return AppLocalizations.of(context)!.waterContentTooltipDry;
  }

  void _onItemTapped(int index) {
    if (_selectedIndex == index) return;

    setState(() {
      _selectedIndex = index;
    });

    switch (index) {
      case 0:
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (context) => const HomeScreen()),
        );
        break;
      case 1:
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
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        AppLocalizations.of(context)!.soilMonitoringDashboard,
                        style: TextStyle(
                          fontFamily: AppConfig.fontFamily,
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          foreground:
                              Paint()
                                ..shader = LinearGradient(
                                  colors: [
                                    AppConfig.primaryColor,
                                    AppConfig.primaryColor,
                                  ],
                                ).createShader(Rect.fromLTWH(0, 0, 200, 70)),
                        ),
                      ),
                      const Spacer(),
                      IconButton(
                        icon: Icon(
                          Icons.refresh,
                          color:
                              AppConfig
                                  .primaryColor, // Changed to primary color
                          size: 30,
                        ),
                        onPressed: () {
                          setState(() {
                            _isLoading = true;
                          });
                          _fetchFieldData();
                        },
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    AppLocalizations.of(context)!.fieldLabel(
                      _fieldData?.fieldName ??
                          AppLocalizations.of(context)!.noFieldSelected,
                    ),
                    style: TextStyle(
                      fontFamily: AppConfig.fontFamily,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppConfig.primaryColor, // Changed to primary color
                    ),
                  ),
                  const SizedBox(height: 16),
                  if (_isLoading)
                    const Center(child: CircularProgressIndicator())
                  else if (_selectedField == null || _fieldData == null)
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(
                        AppLocalizations.of(context)!.noFieldSelectedMessage,
                        style: const TextStyle(
                          fontSize: 16,
                          color: Colors.grey,
                        ),
                      ),
                    )
                  else
                    Column(
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Container(
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(12),
                                  boxShadow: [
                                    BoxShadow(
                                      color: Colors.grey.withOpacity(0.1),
                                      spreadRadius: 1,
                                      blurRadius: 4,
                                      offset: const Offset(0, 2),
                                    ),
                                  ],
                                ),
                                height: 180,
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.start,
                                  children: [
                                    const SizedBox(height: 3),
                                    Text(
                                      AppLocalizations.of(context)!.soilPh,
                                      style: TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        fontSize: 15,
                                        fontWeight: FontWeight.bold,
                                        color:
                                            AppConfig
                                                .primaryColor, // Changed to primary color
                                      ),
                                    ),
                                    const SizedBox(height: 10),
                                    Row(
                                      mainAxisAlignment:
                                          MainAxisAlignment.center,
                                      children: [
                                        Column(
                                          children: [
                                            Container(
                                              width: 25,
                                              height: 20,
                                              decoration: const BoxDecoration(
                                                color: Colors.yellow,
                                                borderRadius: BorderRadius.only(
                                                  topLeft: Radius.circular(8),
                                                  topRight: Radius.circular(8),
                                                ),
                                              ),
                                            ),
                                            Container(
                                              width: 25,
                                              height: 20,
                                              color: Colors.green,
                                            ),
                                            Container(
                                              width: 25,
                                              height: 20,
                                              decoration: const BoxDecoration(
                                                color: Colors.red,
                                                borderRadius: BorderRadius.only(
                                                  bottomLeft: Radius.circular(
                                                    8,
                                                  ),
                                                  bottomRight: Radius.circular(
                                                    8,
                                                  ),
                                                ),
                                              ),
                                            ),
                                          ],
                                        ),
                                        Column(
                                          mainAxisAlignment:
                                              MainAxisAlignment.start,
                                          children: [
                                            Container(
                                              margin: EdgeInsets.only(
                                                top: max(
                                                  0,
                                                  min(
                                                    65,
                                                    (1 -
                                                                (soilPhValue -
                                                                        5) /
                                                                    3) *
                                                            27 -
                                                        5,
                                                  ),
                                                ),
                                              ),
                                              child: const Icon(
                                                Icons.arrow_left,
                                                color: Colors.black,
                                                size: 35,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 8),
                                    Text(
                                      _getPhStatus(soilPhValue),
                                      style: const TextStyle(
                                        fontSize: 15, // Changed to 15
                                        fontWeight: FontWeight.w600,
                                        color: Colors.black,
                                      ),
                                    ),
                                    Text(
                                      soilPhValue.toStringAsFixed(1),
                                      style: const TextStyle(
                                        fontSize: 15, // Changed to 15
                                        fontWeight: FontWeight.bold,
                                        color: Colors.black,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                            const SizedBox(width: 16),
                            Expanded(
                              child: Container(
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(12),
                                  boxShadow: [
                                    BoxShadow(
                                      color: Colors.grey.withOpacity(0.1),
                                      spreadRadius: 1,
                                      blurRadius: 4,
                                      offset: const Offset(0, 2),
                                    ),
                                  ],
                                ),
                                height: 180,
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.start,
                                  children: [
                                    const SizedBox(height: 5),
                                    Text(
                                      AppLocalizations.of(
                                        context,
                                      )!.waterContent,
                                      style: TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        fontSize: 15,
                                        fontWeight: FontWeight.bold,
                                        color:
                                            AppConfig
                                                .primaryColor, // Changed to primary color
                                      ),
                                    ),
                                    const SizedBox(height: 23),
                                    SizedBox(
                                      height: 12,
                                      child: Stack(
                                        children: [
                                          Container(
                                            height: 12,
                                            decoration: BoxDecoration(
                                              color: Colors.grey[200],
                                              borderRadius:
                                                  BorderRadius.circular(6),
                                            ),
                                          ),
                                          FractionallySizedBox(
                                            widthFactor: max(
                                              0,
                                              min(1, (ndwiValue + 1) / 2),
                                            ),
                                            child: Container(
                                              height: 12,
                                              decoration: BoxDecoration(
                                                color: _getWaterContentColor(
                                                  ndwiValue,
                                                ),
                                                borderRadius:
                                                    BorderRadius.circular(6),
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                    const SizedBox(height: 21),
                                    Text(
                                      ndwiValue.toStringAsFixed(3),
                                      style: const TextStyle(
                                        fontSize: 15, // Changed to 15
                                        fontWeight: FontWeight.bold,
                                        color: Colors.black,
                                      ),
                                    ),
                                    Flexible(
                                      child: Text(
                                        _getWaterContentStatus(ndwiValue),
                                        style: const TextStyle(
                                          fontSize: 15, // Changed to 15
                                          fontWeight: FontWeight.w600,
                                          color: Colors.black,
                                        ),
                                        textAlign: TextAlign.center,
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(12),
                            boxShadow: [
                              BoxShadow(
                                color: Colors.grey.withOpacity(0.1),
                                spreadRadius: 1,
                                blurRadius: 4,
                                offset: const Offset(0, 2),
                              ),
                            ],
                          ),
                          height: 120,
                          child: Column(
                            children: [
                              Text(
                                AppLocalizations.of(context)!.organicCarbon,
                                style: TextStyle(
                                  fontFamily: AppConfig.fontFamily,
                                  fontSize: 15,
                                  fontWeight: FontWeight.bold,
                                  color:
                                      AppConfig
                                          .primaryColor, // Changed to primary color
                                ),
                              ),
                              const SizedBox(height: 8),
                              SizedBox(
                                height: 20,
                                child: Stack(
                                  children: [
                                    Container(
                                      height: 12,
                                      decoration: BoxDecoration(
                                        color: Colors.grey[200],
                                        borderRadius: BorderRadius.circular(6),
                                      ),
                                    ),
                                    FractionallySizedBox(
                                      widthFactor: max(
                                        0,
                                        min(1, (organicCarbonValue + 6) / 13),
                                      ),
                                      child: Container(
                                        height: 12,
                                        decoration: BoxDecoration(
                                          color: _getOrganicCarbonColor(
                                            organicCarbonValue,
                                          ),
                                          borderRadius: BorderRadius.circular(
                                            6,
                                          ),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 8),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Text(
                                    organicCarbonValue.toStringAsFixed(2),
                                    style: const TextStyle(
                                      fontSize: 15, // Changed to 15
                                      fontWeight: FontWeight.bold,
                                      color: Colors.black,
                                    ),
                                  ),
                                  const SizedBox(width: 16),
                                  Text(
                                    _getOrganicCarbonStatus(organicCarbonValue),
                                    style: const TextStyle(
                                      fontSize: 15, // Changed to 15
                                      fontWeight: FontWeight.w600,
                                      color: Colors.black,
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        Row(
                          children: [
                            Expanded(
                              child: Container(
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(12),
                                  boxShadow: [
                                    BoxShadow(
                                      color: Colors.grey.withOpacity(0.1),
                                      spreadRadius: 1,
                                      blurRadius: 4,
                                      offset: const Offset(0, 2),
                                    ),
                                  ],
                                ),
                                height: 180,
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Text(
                                      AppLocalizations.of(
                                        context,
                                      )!.landSurfaceTemperature,
                                      style: TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        fontSize: 15,
                                        fontWeight: FontWeight.bold,
                                        color:
                                            AppConfig
                                                .primaryColor, // Changed to primary color
                                      ),
                                      textAlign: TextAlign.center,
                                    ),
                                    const SizedBox(height: 3),
                                    Image.asset(
                                      'assets/images/LST.png',
                                      width: 47,
                                      height: 47,
                                    ),
                                    const SizedBox(height: 3),
                                    Text(
                                      landSurfaceTempValue == null
                                          ? AppLocalizations.of(context)!.na
                                          : '${landSurfaceTempValue.toInt()}°C',
                                      style: const TextStyle(
                                        fontSize: 15,
                                        fontWeight: FontWeight.bold,
                                        color: Colors.black,
                                      ),
                                    ),
                                    Text(
                                      landSurfaceTempValue == null
                                          ? AppLocalizations.of(
                                            context,
                                          )!.dataUnavailable
                                          : _getLSTStatus(landSurfaceTempValue),
                                      style: const TextStyle(
                                        fontSize: 15,
                                        fontWeight: FontWeight.w600,
                                        color: Colors.black,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                            const SizedBox(width: 16),
                            Expanded(
                              child: Container(
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(12),
                                  boxShadow: [
                                    BoxShadow(
                                      color: Colors.grey.withOpacity(0.1),
                                      spreadRadius: 1,
                                      blurRadius: 4,
                                      offset: const Offset(0, 2),
                                    ),
                                  ],
                                ),
                                height: 180,
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.start,
                                  children: [
                                    const SizedBox(height: 10),
                                    Text(
                                      AppLocalizations.of(context)!.soilTexture,
                                      style: TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        fontSize: 15,
                                        fontWeight: FontWeight.bold,
                                        color:
                                            AppConfig
                                                .primaryColor, // Changed to primary color
                                      ),
                                    ),
                                    const SizedBox(height: 11),
                                    Image.asset(
                                      'assets/images/Soil_texture.png',
                                      width: 70,
                                      height: 47,
                                    ),
                                    const SizedBox(height: 13),
                                    Text(
                                      _getLocalizedTexture(soilTextureValue),
                                      style: const TextStyle(
                                        fontSize: 15, // Changed to 15
                                        fontWeight: FontWeight.bold,
                                        color: Colors.black,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        Row(
                          children: [
                            Expanded(
                              child: Container(
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(12),
                                  boxShadow: [
                                    BoxShadow(
                                      color: Colors.grey.withOpacity(0.1),
                                      spreadRadius: 1,
                                      blurRadius: 4,
                                      offset: const Offset(0, 2),
                                    ),
                                  ],
                                ),
                                height: 180,
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Text(
                                      AppLocalizations.of(
                                        context,
                                      )!.soilSalinity,
                                      style: TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        fontSize: 15,
                                        fontWeight: FontWeight.bold,
                                        color:
                                            AppConfig
                                                .primaryColor, // Changed to primary color
                                      ),
                                    ),
                                    const SizedBox(height: 8),
                                    Image.asset(
                                      'assets/images/soil_salinity.png',
                                      width: 47,
                                      height: 47,
                                    ),
                                    const SizedBox(height: 8),
                                    Text(
                                      soilSalinityValue.toStringAsFixed(3),
                                      style: const TextStyle(
                                        fontSize: 15, // Changed to 15
                                        fontWeight: FontWeight.bold,
                                        color: Colors.black,
                                      ),
                                    ),
                                    Text(
                                      _getSalinityStatus(soilSalinityValue),
                                      style: const TextStyle(
                                        fontSize: 15, // Changed to 15
                                        fontWeight: FontWeight.w600,
                                        color: Colors.black,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                            const SizedBox(width: 16),
                            Expanded(
                              child: Container(
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(12),
                                  boxShadow: [
                                    BoxShadow(
                                      color: Colors.grey.withOpacity(0.1),
                                      spreadRadius: 1,
                                      blurRadius: 4,
                                      offset: const Offset(0, 2),
                                    ),
                                  ],
                                ),
                                height: 180,
                                child: Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Image.asset(
                                      'assets/images/Nutrients_holding.png',
                                      width: 47,
                                      height: 47,
                                    ),
                                    const SizedBox(width: 8),
                                    Column(
                                      mainAxisAlignment:
                                          MainAxisAlignment.start,
                                      children: [
                                        const SizedBox(height: 7),
                                        Column(
                                          children: [
                                            Text(
                                              AppLocalizations.of(
                                                context,
                                              )!.nutrientsHoldingCapacityLine1,
                                              style: TextStyle(
                                                fontFamily:
                                                    AppConfig.fontFamily,
                                                fontSize: 14,
                                                fontWeight: FontWeight.bold,
                                                color:
                                                    AppConfig
                                                        .primaryColor, // Changed to primary color
                                              ),
                                              textAlign: TextAlign.center,
                                            ),
                                            Text(
                                              AppLocalizations.of(
                                                context,
                                              )!.nutrientsHoldingCapacityLine2,
                                              style: TextStyle(
                                                fontFamily:
                                                    AppConfig.fontFamily,
                                                fontSize: 14,
                                                fontWeight: FontWeight.bold,
                                                color:
                                                    AppConfig
                                                        .primaryColor, // Changed to primary color
                                              ),
                                              textAlign: TextAlign.center,
                                            ),
                                            Text(
                                              AppLocalizations.of(
                                                context,
                                              )!.nutrientsHoldingCapacityLine3,
                                              style: TextStyle(
                                                fontFamily:
                                                    AppConfig.fontFamily,
                                                fontSize: 14,
                                                fontWeight: FontWeight.bold,
                                                color:
                                                    AppConfig
                                                        .primaryColor, // Changed to primary color
                                              ),
                                              textAlign: TextAlign.center,
                                            ),
                                            Text(
                                              AppLocalizations.of(
                                                context,
                                              )!.nutrientsHoldingCapacityLine4,
                                              style: TextStyle(
                                                fontFamily:
                                                    AppConfig.fontFamily,
                                                fontSize: 14,
                                                fontWeight: FontWeight.bold,
                                                color:
                                                    AppConfig
                                                        .primaryColor, // Changed to primary color
                                              ),
                                              textAlign: TextAlign.center,
                                            ),
                                          ],
                                        ),
                                        const SizedBox(height: 20),
                                        Text(
                                          nutrientsHoldingValue.toStringAsFixed(
                                            1,
                                          ),
                                          style: const TextStyle(
                                            fontSize: 15, // Changed to 15
                                            fontWeight: FontWeight.bold,
                                            color: Colors.black,
                                          ),
                                        ),
                                        Text(
                                          _getCECStatus(nutrientsHoldingValue),
                                          style: const TextStyle(
                                            fontSize: 15, // Changed to 15
                                            fontWeight: FontWeight.w600,
                                            color: Colors.black,
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
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(12),
                            boxShadow: [
                              BoxShadow(
                                color: Colors.grey.withOpacity(0.1),
                                spreadRadius: 1,
                                blurRadius: 4,
                                offset: const Offset(0, 2),
                              ),
                            ],
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Text(
                                    AppLocalizations.of(context)!.insights,
                                    style: TextStyle(
                                      fontFamily: AppConfig.fontFamily,
                                      fontSize: 18,
                                      fontWeight: FontWeight.bold,
                                      color:
                                          AppConfig
                                              .primaryColor, // Changed to primary color
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              RichText(
                                text: TextSpan(
                                  children: [
                                    TextSpan(
                                      text:
                                          AppLocalizations.of(context)!.soilPh,
                                      style: TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                        color:
                                            AppConfig
                                                .primaryColor, // Changed to primary color
                                      ),
                                    ),
                                    TextSpan(
                                      text: ': ',
                                      style: const TextStyle(
                                        fontSize: 16,
                                        color: Colors.black,
                                      ),
                                    ),
                                    TextSpan(
                                      text: _getPhTooltip(soilPhValue),
                                      style: const TextStyle(
                                        fontSize: 16,
                                        color: Colors.black,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 6),
                              RichText(
                                text: TextSpan(
                                  children: [
                                    TextSpan(
                                      text:
                                          AppLocalizations.of(
                                            context,
                                          )!.waterContent,
                                      style: TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                        color:
                                            AppConfig
                                                .primaryColor, // Changed to primary color
                                      ),
                                    ),
                                    TextSpan(
                                      text: ': ',
                                      style: const TextStyle(
                                        fontSize: 16,
                                        color: Colors.black,
                                      ),
                                    ),
                                    TextSpan(
                                      text: _getWaterContentTooltip(ndwiValue),
                                      style: const TextStyle(
                                        fontSize: 16,
                                        color: Colors.black,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 6),
                              RichText(
                                text: TextSpan(
                                  children: [
                                    TextSpan(
                                      text:
                                          AppLocalizations.of(
                                            context,
                                          )!.organicCarbon,
                                      style: TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                        color:
                                            AppConfig
                                                .primaryColor, // Changed to primary color
                                      ),
                                    ),
                                    TextSpan(
                                      text: ': ',
                                      style: const TextStyle(
                                        fontSize: 16,
                                        color: Colors.black,
                                      ),
                                    ),
                                    TextSpan(
                                      text: _getOrganicCarbonTooltip(
                                        organicCarbonValue,
                                      ),
                                      style: const TextStyle(
                                        fontSize: 16,
                                        color: Colors.black,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 6),
                              RichText(
                                text: TextSpan(
                                  children: [
                                    TextSpan(
                                      text:
                                          AppLocalizations.of(
                                            context,
                                          )!.landSurfaceTemperature,
                                      style: TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                        color:
                                            AppConfig
                                                .primaryColor, // Changed to primary color
                                      ),
                                    ),
                                    TextSpan(
                                      text: ': ',
                                      style: const TextStyle(
                                        fontSize: 16,
                                        color: Colors.black,
                                      ),
                                    ),
                                    TextSpan(
                                      text:
                                          landSurfaceTempValue == null
                                              ? AppLocalizations.of(
                                                context,
                                              )!.dataUnavailable
                                              : _getLSTTooltip(
                                                landSurfaceTempValue,
                                              ),
                                      style: const TextStyle(
                                        fontSize: 16,
                                        color: Colors.black,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 6),
                              RichText(
                                text: TextSpan(
                                  children: [
                                    TextSpan(
                                      text:
                                          AppLocalizations.of(
                                            context,
                                          )!.soilTexture,
                                      style: TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                        color:
                                            AppConfig
                                                .primaryColor, // Changed to primary color
                                      ),
                                    ),
                                    TextSpan(
                                      text: ': ',
                                      style: const TextStyle(
                                        fontSize: 16,
                                        color: Colors.black,
                                      ),
                                    ),
                                    TextSpan(
                                      text:
                                          soilTextureValue == null
                                              ? AppLocalizations.of(
                                                context,
                                              )!.dataUnavailable
                                              : _getTextureTooltip(
                                                soilTextureValue,
                                              ),
                                      style: const TextStyle(
                                        fontSize: 16,
                                        color: Colors.black,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 6),
                              RichText(
                                text: TextSpan(
                                  children: [
                                    TextSpan(
                                      text:
                                          AppLocalizations.of(
                                            context,
                                          )!.soilSalinity,
                                      style: TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                        color:
                                            AppConfig
                                                .primaryColor, // Changed to primary color
                                      ),
                                    ),
                                    TextSpan(
                                      text: ': ',
                                      style: const TextStyle(
                                        fontSize: 16,
                                        color: Colors.black,
                                      ),
                                    ),
                                    TextSpan(
                                      text: _getSalinityTooltip(
                                        soilSalinityValue,
                                      ),
                                      style: const TextStyle(
                                        fontSize: 16,
                                        color: Colors.black,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 6),
                              RichText(
                                text: TextSpan(
                                  children: [
                                    TextSpan(
                                      text:
                                          AppLocalizations.of(
                                            context,
                                          )!.nutrientsHoldingCapacity,
                                      style: TextStyle(
                                        fontFamily: AppConfig.fontFamily,
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                        color:
                                            AppConfig
                                                .primaryColor, // Changed to primary color
                                      ),
                                    ),
                                    TextSpan(
                                      text: ': ',
                                      style: const TextStyle(
                                        fontSize: 16,
                                        color: Colors.black,
                                      ),
                                    ),
                                    TextSpan(
                                      text: _getCECTooltip(
                                        nutrientsHoldingValue,
                                      ),
                                      style: const TextStyle(
                                        fontSize: 16,
                                        color: Colors.black,
                                      ),
                                    ),
                                  ],
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
          ],
        ),
      ),
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
