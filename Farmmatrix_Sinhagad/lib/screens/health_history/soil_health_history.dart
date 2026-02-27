// import 'dart:convert';
// import 'dart:typed_data';
// import 'package:flutter/material.dart';
// import 'package:flutter_dotenv/flutter_dotenv.dart';
// import 'package:http/http.dart' as http;
// import 'package:intl/intl.dart';
// import 'package:farmmatrix/l10n/app_localizations.dart';
// import 'package:farmmatrix/services/field_services.dart';

// class SoilHealthHistoryScreen extends StatefulWidget {
//   final String fieldId;

//   const SoilHealthHistoryScreen({super.key, required this.fieldId});

//   @override
//   State<SoilHealthHistoryScreen> createState() =>
//       _SoilHealthHistoryScreenState();
// }

// class _SoilHealthHistoryScreenState extends State<SoilHealthHistoryScreen> {
//   final FieldService _fieldService = FieldService();

//   Uint8List? _chartImage;
//   String? _aiInsight;

//   bool _loading = false;
//   bool _hasSelection = false;

//   String? _selectedParam; // UI display name
//   String? _apiParam; // exact API parameter name
//   DateTime? _startDate;
//   DateTime? _endDate;

//   // UI label → API exact name (case-sensitive as provided)
//   static const Map<String, String> _paramToApi = {
//     "Overall Soil Health Score (ICAR)": "Soil Health Score",
//     "Soil pH": "pH",
//     "Salinity / EC (mS/cm)": "Salinity",
//     "Organic Carbon (%)": "Organic Carbon",
//     "Cation Exchange Capacity (cmol/kg)": "CEC",
//     "Land Surface Temperature (°C)": "LST",
//     "NDVI — Vegetation Density": "NDVI",
//     "EVI — Enhanced Vegetation Index": "EVI",
//     "FVC — Fractional Vegetation Cover": "FVC",
//     "NDWI — Soil Moisture Index": "NDWI",
//     "Nitrogen (kg/ha)": "Nitrogen",
//     "Phosphorus (kg/ha)": "Phosphorus",
//     "Potassium (kg/ha)": "Potassium",
//     "Calcium (kg/ha)": "Calcium",
//     "Magnesium (kg/ha)": "Magnesium",
//     "Sulphur (kg/ha)": "Sulphur",
//   };

//   Future<void> _fetchData() async {
//     if (_selectedParam == null || _startDate == null || _endDate == null)
//       return;

//     final apiParam = _paramToApi[_selectedParam];
//     if (apiParam == null) {
//       print("ERROR: No API mapping found for '$_selectedParam'");
//       setState(() => _loading = false);
//       return;
//     }

//     setState(() {
//       _loading = true;
//       _chartImage = null;
//       _aiInsight = null;
//       _apiParam = apiParam;
//     });

//     try {
//       final field = await _fieldService.getFieldData(widget.fieldId);
//       if (field == null || field.geometry == null) {
//         print("Field geometry missing");
//         setState(() => _loading = false);
//         return;
//       }

//       // ────────────────────────────────────────────────
//       // Coordinate conversion - MATCHING YOUR WORKING REPORT SCREEN
//       // Assumption: stored as [latitude, longitude]
//       // API expects: [longitude, latitude]
//       // ────────────────────────────────────────────────
//       final coordinates = field.geometry!['coordinates'][0] as List<dynamic>;

//       final List<List<double>> apiCoords = [];

//       // Debug: show what is actually stored
//       print("\n=== RAW COORDINATES FROM DATABASE (first 4 points) ===");
//       for (int i = 0; i < coordinates.length && i < 4; i++) {
//         final point = coordinates[i] as List<dynamic>;
//         print("  Point $i: lat=${point[0]}, lon=${point[1]}");
//       }

//       for (var item in coordinates) {
//         final lat = (item[0] as num).toDouble(); // stored latitude
//         final lng = (item[1] as num).toDouble(); // stored longitude

//         // Swap → API wants [longitude, latitude]
//         apiCoords.add([lng, lat]);
//       }

//       // Close the polygon if not already closed
//       if (apiCoords.isNotEmpty && apiCoords.first != apiCoords.last) {
//         apiCoords.add(apiCoords.first);
//       }

//       // Debug: confirm what we are sending
//       print("\n=== SENT TO API [lon, lat] (first 4 points) ===");
//       for (int i = 0; i < apiCoords.length && i < 4; i++) {
//         print("  Point $i: ${apiCoords[i][0]}, ${apiCoords[i][1]}");
//       }
//       print("Total points sent: ${apiCoords.length}\n");

//       final commonPayload = {
//         "coordinates": [apiCoords],
//         "start_date": DateFormat('yyyy-MM-dd').format(_startDate!),
//         "end_date": DateFormat('yyyy-MM-dd').format(_endDate!),
//         "selected_param": apiParam,
//         "location": "Field",
//         "include_chart": true,
//         "include_insight": true,
//       };

//       // ────────────────────────────────────────────────
//       // 1. ANALYSE API (for insight & summary)
//       // ────────────────────────────────────────────────
//       final analyseUrl = dotenv.env['SOIL_HEALTH_ANALYSE_API'];
//       if (analyseUrl != null && analyseUrl.isNotEmpty) {
//         print("======== ANALYSE API REQUEST ========");
//         print(jsonEncode(commonPayload));
//         print("======================================");

//         final analyseRes = await http.post(
//           Uri.parse(analyseUrl),
//           headers: {"Content-Type": "application/json"},
//           body: jsonEncode(commonPayload),
//         );

//         print("ANALYSE Status: ${analyseRes.statusCode}");
//         _logChunked("ANALYSE RESPONSE", analyseRes.body);

//         if (analyseRes.statusCode == 200) {
//           final body = jsonDecode(analyseRes.body);
//           final insightText = body["ai_insight"]?["text"] as String?;
//           setState(() {
//             _aiInsight =
//                 insightText?.isNotEmpty == true
//                     ? insightText
//                     : "No insight returned from analyse API";
//           });
//         }
//       } else {
//         print("SOIL_HEALTH_ANALYSE_API missing in .env");
//       }

//       // ────────────────────────────────────────────────
//       // 2. CHART API (dedicated chart endpoint)
//       // ────────────────────────────────────────────────
//       // ────────────────────────────────────────────────
//       // 2. CHART API – now expects RAW PNG, not JSON
//       // ────────────────────────────────────────────────
//       final chartUrl = dotenv.env['SOIL_HEALTH_CHART_API'];
//       if (chartUrl != null && chartUrl.isNotEmpty) {
//         print("======== CHART API REQUEST (raw PNG expected) ========");
//         print(jsonEncode(commonPayload));
//         print("====================================================");

//         final chartResponse = await http.post(
//           Uri.parse(chartUrl),
//           headers: {"Content-Type": "application/json"},
//           body: jsonEncode(commonPayload),
//         );

//         print("CHART Status: ${chartResponse.statusCode}");
//         print(
//           "CHART Content-Type: ${chartResponse.headers['content-type'] ?? 'unknown'}",
//         );
//         print("CHART Body length: ${chartResponse.bodyBytes.length} bytes");

//         if (chartResponse.statusCode == 200) {
//           final contentType =
//               chartResponse.headers['content-type']?.toLowerCase() ?? '';

//           if (contentType.contains('image/png') ||
//               (contentType.isEmpty && chartResponse.bodyBytes.isNotEmpty)) {
//             // Treat as raw image bytes
//             final imageBytes = chartResponse.bodyBytes;
//             print(
//               "Received raw PNG (${imageBytes.length} bytes) → using directly",
//             );

//             // Optional: quick sanity check (PNG signature)
//             if (imageBytes.length >= 8 &&
//                 imageBytes[1] == 0x50 &&
//                 imageBytes[2] == 0x4E &&
//                 imageBytes[3] == 0x47) {
//               print("PNG signature detected → looks valid");
//             } else {
//               print(
//                 "Warning: Does NOT look like a valid PNG (missing signature)",
//               );
//             }

//             setState(() => _chartImage = imageBytes);
//           } else if (contentType.contains('application/json')) {
//             // Fallback: old behavior (if someone redeploys the endpoint)
//             try {
//               final body = jsonDecode(chartResponse.body);
//               final base64Str = body["chart"]?["image"] as String?;
//               if (base64Str != null && base64Str.isNotEmpty) {
//                 final bytes = base64Decode(base64Str);
//                 print("Fallback: decoded base64 chart (${bytes.length} bytes)");
//                 setState(() => _chartImage = bytes);
//               }
//             } catch (e) {
//               print("JSON fallback failed: $e");
//             }
//           } else {
//             print("Unexpected content-type: $contentType");
//           }
//         } else {
//           print("CHART API failed with status ${chartResponse.statusCode}");
//           _logChunked("CHART ERROR RESPONSE", chartResponse.body);
//         }
//       } else {
//         print("SOIL_HEALTH_CHART_API missing in .env");
//       }
//     } catch (e, stack) {
//       print("FETCH ERROR: $e");
//       print("Stack: $stack");
//     } finally {
//       if (mounted) {
//         setState(() => _loading = false);
//       }
//     }
//   }

//   void _logChunked(String label, String body) {
//     print("======== $label START ========");
//     const chunk = 800;
//     for (int i = 0; i < body.length; i += chunk) {
//       final end = i + chunk < body.length ? i + chunk : body.length;
//       print(body.substring(i, end));
//     }
//     print("======== $label END ========");
//   }

//   void _openFilterDialog() {
//     showDialog(
//       context: context,
//       builder:
//           (context) => FilterDialog(
//             onApply: (param, start, end) {
//               setState(() {
//                 _selectedParam = param;
//                 _startDate = start;
//                 _endDate = end;
//                 _hasSelection = true;
//               });
//               Navigator.pop(context);
//               _fetchData();
//             },
//           ),
//     );
//   }

//   @override
//   Widget build(BuildContext context) {
//     final loc = AppLocalizations.of(context)!;

//     return Scaffold(
//       appBar: AppBar(
//         title: Text(loc.soilHealthHistory),
//         backgroundColor: const Color(0xFF1B413C),
//       ),
//       body: Column(
//         children: [
//           // Chart container
//           Padding(
//             padding: const EdgeInsets.all(16),
//             child: Container(
//               height: 220,
//               width: double.infinity,
//               decoration: BoxDecoration(
//                 color: Colors.white,
//                 borderRadius: BorderRadius.circular(12),
//               ),
//               child:
//                   _loading
//                       ? const Center(child: CircularProgressIndicator())
//                       : !_hasSelection
//                       ? Center(
//                         child: Text(
//                           loc.pleaseSelectParameter,
//                           style: const TextStyle(color: Colors.grey),
//                         ),
//                       )
//                       : _chartImage != null
//                       ? Image.memory(_chartImage!, fit: BoxFit.contain)
//                       : Center(child: Text(loc.noDataAvailable)),
//             ),
//           ),

//           // Selected info
//           if (_hasSelection && _startDate != null && _endDate != null)
//             Padding(
//               padding: const EdgeInsets.symmetric(horizontal: 16),
//               child: Row(
//                 mainAxisAlignment: MainAxisAlignment.spaceBetween,
//                 children: [
//                   Text(
//                     _selectedParam ?? "",
//                     style: const TextStyle(fontWeight: FontWeight.bold),
//                   ),
//                   Text(
//                     "${DateFormat('dd MMM').format(_startDate!)} - ${DateFormat('dd MMM').format(_endDate!)}",
//                   ),
//                 ],
//               ),
//             ),

//           const SizedBox(height: 16),

//           // Summary title
//           Padding(
//             padding: const EdgeInsets.symmetric(horizontal: 16),
//             child: Align(
//               alignment: Alignment.centerLeft,
//               child: Text(
//                 loc.summary,
//                 style: const TextStyle(
//                   fontSize: 18,
//                   fontWeight: FontWeight.bold,
//                 ),
//               ),
//             ),
//           ),

//           const SizedBox(height: 8),

//           // Insight / summary text
//           Expanded(
//             child: Padding(
//               padding: const EdgeInsets.all(16),
//               child:
//                   _loading
//                       ? const SizedBox()
//                       : !_hasSelection
//                       ? Center(child: Text(loc.pleaseSelectParameter))
//                       : SingleChildScrollView(
//                         child: Text(_aiInsight ?? loc.noDataAvailable),
//                       ),
//             ),
//           ),

//           // Filter button
//           Padding(
//             padding: const EdgeInsets.all(16),
//             child: ElevatedButton.icon(
//               style: ElevatedButton.styleFrom(
//                 backgroundColor: const Color(0xFFFFD358),
//                 foregroundColor: Colors.black,
//                 minimumSize: const Size(double.infinity, 50),
//               ),
//               icon: const Icon(Icons.tune),
//               label: Text(loc.filter),
//               onPressed: _openFilterDialog,
//             ),
//           ),
//         ],
//       ),
//     );
//   }
// }

// // ────────────────────────────────────────────────
// // Filter Dialog (unchanged except minor safety)
// // ────────────────────────────────────────────────
// class FilterDialog extends StatefulWidget {
//   final Function(String, DateTime, DateTime) onApply;

//   const FilterDialog({super.key, required this.onApply});

//   @override
//   State<FilterDialog> createState() => _FilterDialogState();
// }

// class _FilterDialogState extends State<FilterDialog> {
//   String? _selectedParam;
//   bool _isLastMonth = true;
//   DateTime? _startDate;
//   DateTime? _endDate;

//   final List<String> parameters = [
//     "Overall Soil Health Score (ICAR)",
//     "Soil pH",
//     "Salinity / EC (mS/cm)",
//     "Organic Carbon (%)",
//     "Cation Exchange Capacity (cmol/kg)",
//     "Land Surface Temperature (°C)",
//     "NDVI — Vegetation Density",
//     "EVI — Enhanced Vegetation Index",
//     "FVC — Fractional Vegetation Cover",
//     "NDWI — Soil Moisture Index",
//     "Nitrogen (kg/ha)",
//     "Phosphorus (kg/ha)",
//     "Potassium (kg/ha)",
//     "Calcium (kg/ha)",
//     "Magnesium (kg/ha)",
//     "Sulphur (kg/ha)",
//   ];

//   @override
//   void initState() {
//     super.initState();
//     final now = DateTime.now();
//     _endDate = now;
//     _startDate = now.subtract(const Duration(days: 30));
//   }

//   Future<void> _pickStartDate() async {
//     final picked = await showDatePicker(
//       context: context,
//       initialDate: _startDate ?? DateTime.now(),
//       firstDate: DateTime(2020),
//       lastDate: DateTime.now(),
//     );
//     if (picked != null && mounted) {
//       setState(() {
//         _startDate = picked;
//         _isLastMonth = false;
//       });
//     }
//   }

//   Future<void> _pickEndDate() async {
//     final picked = await showDatePicker(
//       context: context,
//       initialDate: _endDate ?? DateTime.now(),
//       firstDate: _startDate ?? DateTime(2020),
//       lastDate: DateTime.now(),
//     );
//     if (picked != null && mounted) {
//       setState(() {
//         _endDate = picked;
//         _isLastMonth = false;
//       });
//     }
//   }

//   @override
//   Widget build(BuildContext context) {
//     final loc = AppLocalizations.of(context)!;

//     return Dialog(
//       insetPadding: const EdgeInsets.symmetric(horizontal: 16),
//       shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
//       child: Container(
//         padding: const EdgeInsets.all(20),
//         decoration: BoxDecoration(
//           borderRadius: BorderRadius.circular(24),
//           color: Colors.white,
//         ),
//         child: SingleChildScrollView(
//           child: Column(
//             crossAxisAlignment: CrossAxisAlignment.start,
//             children: [
//               Text(
//                 loc.selectSoilParameter,
//                 style: const TextStyle(
//                   fontSize: 18,
//                   fontWeight: FontWeight.w600,
//                 ),
//               ),
//               const SizedBox(height: 16),

//               Wrap(
//                 spacing: 10,
//                 runSpacing: 10,
//                 children:
//                     parameters.map((param) {
//                       final selected = _selectedParam == param;
//                       return GestureDetector(
//                         onTap:
//                             () => setState(
//                               () => _selectedParam = selected ? null : param,
//                             ),
//                         child: Container(
//                           padding: const EdgeInsets.symmetric(
//                             horizontal: 14,
//                             vertical: 8,
//                           ),
//                           decoration: BoxDecoration(
//                             color:
//                                 selected ? Colors.white : Colors.grey.shade100,
//                             borderRadius: BorderRadius.circular(24),
//                             border: Border.all(
//                               color:
//                                   selected
//                                       ? const Color(0xFF1B413C)
//                                       : Colors.grey.shade400,
//                               width: 1.2,
//                             ),
//                           ),
//                           child: Row(
//                             mainAxisSize: MainAxisSize.min,
//                             children: [
//                               if (selected) ...[
//                                 const Icon(Icons.close, size: 16),
//                                 const SizedBox(width: 6),
//                               ],
//                               Text(
//                                 param,
//                                 style: TextStyle(
//                                   fontWeight:
//                                       selected
//                                           ? FontWeight.w600
//                                           : FontWeight.normal,
//                                 ),
//                               ),
//                             ],
//                           ),
//                         ),
//                       );
//                     }).toList(),
//               ),

//               const SizedBox(height: 28),

//               Text(
//                 loc.selectDateRange,
//                 style: const TextStyle(
//                   fontSize: 18,
//                   fontWeight: FontWeight.w600,
//                 ),
//               ),
//               const SizedBox(height: 16),

//               GestureDetector(
//                 onTap: () {
//                   final now = DateTime.now();
//                   setState(() {
//                     _isLastMonth = true;
//                     _endDate = now;
//                     _startDate = now.subtract(const Duration(days: 30));
//                   });
//                 },
//                 child: Container(
//                   padding: const EdgeInsets.symmetric(
//                     horizontal: 14,
//                     vertical: 8,
//                   ),
//                   decoration: BoxDecoration(
//                     borderRadius: BorderRadius.circular(24),
//                     border: Border.all(
//                       color:
//                           _isLastMonth
//                               ? const Color(0xFF1B413C)
//                               : Colors.grey.shade400,
//                     ),
//                   ),
//                   child: Row(
//                     mainAxisSize: MainAxisSize.min,
//                     children: [
//                       if (_isLastMonth) ...[
//                         const Icon(Icons.close, size: 16),
//                         const SizedBox(width: 6),
//                       ],
//                       Text(
//                         loc.lastMonth,
//                         style: TextStyle(
//                           fontWeight:
//                               _isLastMonth
//                                   ? FontWeight.w600
//                                   : FontWeight.normal,
//                         ),
//                       ),
//                     ],
//                   ),
//                 ),
//               ),

//               const SizedBox(height: 18),

//               Row(
//                 children: [
//                   const Icon(
//                     Icons.calendar_today,
//                     size: 18,
//                     color: Colors.grey,
//                   ),
//                   const SizedBox(width: 8),
//                   Text(loc.custom, style: const TextStyle(color: Colors.grey)),
//                 ],
//               ),
//               const SizedBox(height: 12),

//               GestureDetector(
//                 onTap: () async {
//                   await _pickStartDate();
//                   if (_startDate != null) await _pickEndDate();
//                 },
//                 child: Container(
//                   padding: const EdgeInsets.symmetric(
//                     horizontal: 16,
//                     vertical: 14,
//                   ),
//                   decoration: BoxDecoration(
//                     borderRadius: BorderRadius.circular(24),
//                     border: Border.all(color: Colors.grey.shade400),
//                   ),
//                   child: Row(
//                     mainAxisAlignment: MainAxisAlignment.spaceBetween,
//                     children: [
//                       Text(
//                         _startDate == null
//                             ? "Start date"
//                             : "${_startDate!.day}/${_startDate!.month}/${_startDate!.year}",
//                       ),
//                       const Icon(Icons.arrow_forward),
//                       Text(
//                         _endDate == null
//                             ? "End date"
//                             : "${_endDate!.day}/${_endDate!.month}/${_endDate!.year}",
//                       ),
//                     ],
//                   ),
//                 ),
//               ),

//               const SizedBox(height: 28),

//               SizedBox(
//                 width: double.infinity,
//                 child: ElevatedButton(
//                   style: ElevatedButton.styleFrom(
//                     backgroundColor: const Color(0xFF1B413C),
//                     foregroundColor: Colors.white,
//                     padding: const EdgeInsets.symmetric(vertical: 14),
//                     shape: RoundedRectangleBorder(
//                       borderRadius: BorderRadius.circular(30),
//                     ),
//                   ),
//                   onPressed:
//                       _selectedParam == null ||
//                               _startDate == null ||
//                               _endDate == null
//                           ? null
//                           : () => widget.onApply(
//                             _selectedParam!,
//                             _startDate!,
//                             _endDate!,
//                           ),
//                   child: Text(loc.apply),
//                 ),
//               ),
//             ],
//           ),
//         ),
//       ),
//     );
//   }
// }


import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:http/http.dart' as http;
import 'package:intl/intl.dart';
import 'package:farmmatrix/l10n/app_localizations.dart';
import 'package:farmmatrix/services/field_services.dart';

class SoilHealthHistoryScreen extends StatefulWidget {
  final String fieldId;

  const SoilHealthHistoryScreen({super.key, required this.fieldId});

  @override
  State<SoilHealthHistoryScreen> createState() => _SoilHealthHistoryScreenState();
}

class _SoilHealthHistoryScreenState extends State<SoilHealthHistoryScreen> {
  final FieldService _fieldService = FieldService();

  Uint8List? _chartImage;
  String? _aiInsight;

  bool _loading = false;
  bool _hasSelection = false;

  String? _selectedParam;
  String? _apiParam;
  DateTime? _startDate;
  DateTime? _endDate;

  bool _isLandscape = false;

  static const Map<String, String> _paramToApi = {
    "Overall Soil Health Score (ICAR)": "Soil Health Score",
    "Soil pH": "pH",
    "Salinity / EC (mS/cm)": "Salinity",
    "Organic Carbon (%)": "Organic Carbon",
    "Cation Exchange Capacity (cmol/kg)": "CEC",
    "Land Surface Temperature (°C)": "LST",
    "NDVI — Vegetation Density": "NDVI",
    "EVI — Enhanced Vegetation Index": "EVI",
    "FVC — Fractional Vegetation Cover": "FVC",
    "NDWI — Soil Moisture Index": "NDWI",
    "Nitrogen (kg/ha)": "Nitrogen",
    "Phosphorus (kg/ha)": "Phosphorus",
    "Potassium (kg/ha)": "Potassium",
    "Calcium (kg/ha)": "Calcium",
    "Magnesium (kg/ha)": "Magnesium",
    "Sulphur (kg/ha)": "Sulphur",
  };

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _updateOrientationState();
    });
  }

  void _updateOrientationState() {
    if (!mounted) return;
    final orientation = MediaQuery.of(context).orientation;
    setState(() {
      _isLandscape = orientation == Orientation.landscape;
    });
  }

  Future<void> _toggleOrientation() async {
    if (_isLandscape) {
      await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
    } else {
      await SystemChrome.setPreferredOrientations([
        DeviceOrientation.landscapeLeft,
        DeviceOrientation.landscapeRight,
      ]);
    }

    await Future.delayed(const Duration(milliseconds: 300));
    _updateOrientationState();
  }

  // Reset to portrait when leaving the screen
  Future<bool> _onWillPop() async {
    await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
    return true;
  }

  Future<void> _fetchData() async {
    if (_selectedParam == null || _startDate == null || _endDate == null) return;

    final apiParam = _paramToApi[_selectedParam];
    if (apiParam == null) {
      print("ERROR: No mapping for '$_selectedParam'");
      setState(() => _loading = false);
      return;
    }

    setState(() {
      _loading = true;
      _chartImage = null;
      _aiInsight = null;
      _apiParam = apiParam;
    });

    try {
      final field = await _fieldService.getFieldData(widget.fieldId);
      if (field == null || field.geometry == null) {
        print("Field geometry missing");
        return;
      }

      final coordinates = field.geometry!['coordinates'][0] as List<dynamic>;
      final List<List<double>> apiCoords = [];

      for (var item in coordinates) {
        final lat = (item[0] as num).toDouble();
        final lng = (item[1] as num).toDouble();
        apiCoords.add([lng, lat]);
      }

      if (apiCoords.isNotEmpty && apiCoords.first != apiCoords.last) {
        apiCoords.add(apiCoords.first);
      }

      final payload = {
        "coordinates": [apiCoords],
        "start_date": DateFormat('yyyy-MM-dd').format(_startDate!),
        "end_date": DateFormat('yyyy-MM-dd').format(_endDate!),
        "selected_param": apiParam,
        "location": "Field",
        "include_chart": true,
        "include_insight": true,
      };

      // Analyse API (JSON)
      final analyseUrl = dotenv.env['SOIL_HEALTH_ANALYSE_API'];
      if (analyseUrl != null && analyseUrl.isNotEmpty) {
        final res = await http.post(Uri.parse(analyseUrl),
            headers: {"Content-Type": "application/json"}, body: jsonEncode(payload));
        if (res.statusCode == 200) {
          final body = jsonDecode(res.body);
          _aiInsight = body["ai_insight"]?["text"] as String?;
        }
      }

      // Chart API (raw PNG)
      final chartUrl = dotenv.env['SOIL_HEALTH_CHART_API'];
      if (chartUrl != null && chartUrl.isNotEmpty) {
        final chartRes = await http.post(Uri.parse(chartUrl),
            headers: {"Content-Type": "application/json"}, body: jsonEncode(payload));
        if (chartRes.statusCode == 200) {
          final contentType = chartRes.headers['content-type']?.toLowerCase() ?? '';
          if (contentType.contains('image/png') || chartRes.bodyBytes.isNotEmpty) {
            _chartImage = chartRes.bodyBytes;
          }
        }
      }
    } catch (e) {
      print("Fetch error: $e");
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _openFilterDialog() {
    showDialog(
      context: context,
      builder: (context) => FilterDialog(
        onApply: (param, start, end) {
          setState(() {
            _selectedParam = param;
            _startDate = start;
            _endDate = end;
            _hasSelection = true;
          });
          Navigator.pop(context);
          _fetchData();
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    final isPortrait = MediaQuery.of(context).orientation == Orientation.portrait;

    return WillPopScope(
      onWillPop: _onWillPop,
      child: Scaffold(
        backgroundColor: const Color(0xFFF5F5F5),
        appBar: AppBar(
          title: Text(loc.soilHealthHistory),
          backgroundColor: const Color(0xFF1B413C),
        ),
        body: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Chart area
              Padding(
                padding: const EdgeInsets.all(16),
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Container(
                      constraints: BoxConstraints(
                        minHeight: isPortrait ? 280 : 400,
                        maxHeight: isPortrait ? 340 : double.infinity,
                      ),
                      width: double.infinity,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(0.08),
                            blurRadius: 12,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: _loading
                          ? const Center(child: CircularProgressIndicator())
                          : !_hasSelection
                              ? Center(
                                  child: Text(
                                    loc.pleaseSelectParameter,
                                    style: const TextStyle(color: Colors.grey),
                                  ),
                                )
                              : _chartImage != null
                                  ? isPortrait
                                      ? ClipRRect(
                                          borderRadius: BorderRadius.circular(16),
                                          child: InteractiveViewer(
                                            boundaryMargin: const EdgeInsets.all(40),
                                            minScale: 0.6,
                                            maxScale: 4.5,
                                            child: Image.memory(
                                              _chartImage!,
                                              fit: BoxFit.contain,
                                              alignment: Alignment.center,
                                            ),
                                          ),
                                        )
                                      : Image.memory(
                                          _chartImage!,
                                          fit: BoxFit.contain,
                                        )
                                  : Center(child: Text(loc.noDataAvailable)),
                    ),

                    // Rotate icon
                    if (_hasSelection && _chartImage != null)
                      Positioned(
                        top: 12,
                        right: 12,
                        child: Material(
                          color: Colors.white.withOpacity(0.92),
                          borderRadius: BorderRadius.circular(30),
                          elevation: 3,
                          child: InkWell(
                            borderRadius: BorderRadius.circular(30),
                            onTap: _toggleOrientation,
                            child: Padding(
                              padding: const EdgeInsets.all(10),
                              child: Icon(
                                _isLandscape ? Icons.rotate_left_rounded : Icons.rotate_right_rounded,
                                size: 28,
                                color: const Color(0xFF1B413C),
                              ),
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),

              // Info row – only portrait
              if (isPortrait && _hasSelection && _startDate != null && _endDate != null)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        _selectedParam ?? "",
                        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
                      ),
                      Text(
                        "${DateFormat('dd MMM').format(_startDate!)} – ${DateFormat('dd MMM').format(_endDate!)}",
                        style: const TextStyle(fontSize: 14),
                      ),
                    ],
                  ),
                ),

              if (isPortrait) const SizedBox(height: 12),

              // Summary title
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    loc.summary,
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ),
              ),

              const SizedBox(height: 10),

              // Summary content
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: _loading
                    ? const Center(child: CircularProgressIndicator())
                    : !_hasSelection
                        ? Center(child: Text(loc.pleaseSelectParameter))
                        : Text(
                            _aiInsight ?? loc.noDataAvailable,
                            style: const TextStyle(height: 1.5, fontSize: 15),
                          ),
              ),

              const SizedBox(height: 20),

              // Filter button
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 32),
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFFFD358),
                    foregroundColor: Colors.black,
                    minimumSize: const Size(double.infinity, 54),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    elevation: 2,
                  ),
                  icon: const Icon(Icons.tune, size: 22),
                  label: Text(
                    loc.filter,
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                  onPressed: _openFilterDialog,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    // Final safety reset to portrait when widget is disposed
    SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
    super.dispose();
  }
}

class FilterDialog extends StatefulWidget {
  final Function(String, DateTime, DateTime) onApply;

  const FilterDialog({super.key, required this.onApply});

  @override
  State<FilterDialog> createState() => _FilterDialogState();
}

class _FilterDialogState extends State<FilterDialog> {
  String? _selectedParam;
  bool _isLastMonth = true;
  DateTime? _startDate;
  DateTime? _endDate;

  final List<String> parameters = [
    "Overall Soil Health Score (ICAR)",
    "Soil pH",
    "Salinity / EC (mS/cm)",
    "Organic Carbon (%)",
    "Cation Exchange Capacity (cmol/kg)",
    "Land Surface Temperature (°C)",
    "NDVI — Vegetation Density",
    "EVI — Enhanced Vegetation Index",
    "FVC — Fractional Vegetation Cover",
    "NDWI — Soil Moisture Index",
    "Nitrogen (kg/ha)",
    "Phosphorus (kg/ha)",
    "Potassium (kg/ha)",
    "Calcium (kg/ha)",
    "Magnesium (kg/ha)",
    "Sulphur (kg/ha)",
  ];

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _endDate = now;
    _startDate = now.subtract(const Duration(days: 30));
  }

  Future<void> _pickStartDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _startDate ?? DateTime.now(),
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
    );
    if (picked != null && mounted) {
      setState(() {
        _startDate = picked;
        _isLastMonth = false;
      });
    }
  }

  Future<void> _pickEndDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _endDate ?? DateTime.now(),
      firstDate: _startDate ?? DateTime(2020),
      lastDate: DateTime.now(),
    );
    if (picked != null && mounted) {
      setState(() {
        _endDate = picked;
        _isLastMonth = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;

    return Dialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(24),
          color: Colors.white,
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                loc.selectSoilParameter,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 16),

              Wrap(
                spacing: 10,
                runSpacing: 10,
                children:
                    parameters.map((param) {
                      final selected = _selectedParam == param;
                      return GestureDetector(
                        onTap:
                            () => setState(
                              () => _selectedParam = selected ? null : param,
                            ),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 8,
                          ),
                          decoration: BoxDecoration(
                            color:
                                selected ? Colors.white : Colors.grey.shade100,
                            borderRadius: BorderRadius.circular(24),
                            border: Border.all(
                              color:
                                  selected
                                      ? const Color(0xFF1B413C)
                                      : Colors.grey.shade400,
                              width: 1.2,
                            ),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              if (selected) ...[
                                const Icon(Icons.close, size: 16),
                                const SizedBox(width: 6),
                              ],
                              Text(
                                param,
                                style: TextStyle(
                                  fontWeight:
                                      selected
                                          ? FontWeight.w600
                                          : FontWeight.normal,
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    }).toList(),
              ),

              const SizedBox(height: 28),

              Text(
                loc.selectDateRange,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 16),

              GestureDetector(
                onTap: () {
                  final now = DateTime.now();
                  setState(() {
                    _isLastMonth = true;
                    _endDate = now;
                    _startDate = now.subtract(const Duration(days: 30));
                  });
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(
                      color:
                          _isLastMonth
                              ? const Color(0xFF1B413C)
                              : Colors.grey.shade400,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (_isLastMonth) ...[
                        const Icon(Icons.close, size: 16),
                        const SizedBox(width: 6),
                      ],
                      Text(
                        loc.lastMonth,
                        style: TextStyle(
                          fontWeight:
                              _isLastMonth
                                  ? FontWeight.w600
                                  : FontWeight.normal,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 18),

              Row(
                children: [
                  const Icon(
                    Icons.calendar_today,
                    size: 18,
                    color: Colors.grey,
                  ),
                  const SizedBox(width: 8),
                  Text(loc.custom, style: const TextStyle(color: Colors.grey)),
                ],
              ),
              const SizedBox(height: 12),

              GestureDetector(
                onTap: () async {
                  await _pickStartDate();
                  if (_startDate != null) await _pickEndDate();
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 14,
                  ),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: Colors.grey.shade400),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        _startDate == null
                            ? "Start date"
                            : "${_startDate!.day}/${_startDate!.month}/${_startDate!.year}",
                      ),
                      const Icon(Icons.arrow_forward),
                      Text(
                        _endDate == null
                            ? "End date"
                            : "${_endDate!.day}/${_endDate!.month}/${_endDate!.year}",
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 28),

              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1B413C),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(30),
                    ),
                  ),
                  onPressed:
                      _selectedParam == null ||
                              _startDate == null ||
                              _endDate == null
                          ? null
                          : () => widget.onApply(
                            _selectedParam!,
                            _startDate!,
                            _endDate!,
                          ),
                  child: Text(loc.apply),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

