import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:http/http.dart' as http;
import 'package:intl/intl.dart';
import 'package:farmmatrix/l10n/app_localizations.dart';
import 'package:farmmatrix/services/field_services.dart';

class SoilHealthHistoryScreen extends StatefulWidget {
  final String fieldId;

  const SoilHealthHistoryScreen({super.key, required this.fieldId});

  @override
  State<SoilHealthHistoryScreen> createState() =>
      _SoilHealthHistoryScreenState();
}

class _SoilHealthHistoryScreenState extends State<SoilHealthHistoryScreen> {
  final FieldService _fieldService = FieldService();

  Uint8List? _chartImage;
  String? _aiInsight;

  bool _loading = false;
  bool _hasSelection = false;

  String? _selectedParam;
  DateTime? _startDate;
  DateTime? _endDate;

  /// =========================
  /// API CALL
  /// =========================
  Future<void> _fetchData() async {
    if (_selectedParam == null || _startDate == null || _endDate == null) {
      return;
    }

    setState(() => _loading = true);

    try {
      final apiUrl = dotenv.env['SOIL_HEALTH_HISTORY_API'];
      if (apiUrl == null) {
        print("API URL missing");
        setState(() => _loading = false);
        return;
      }

      final field = await _fieldService.getFieldData(widget.fieldId);

      if (field == null || field.geometry == null) {
        print("Field geometry missing");
        setState(() => _loading = false);
        return;
      }

      final payload = {
        "coordinates": [field.geometry!['coordinates'][0]],
        "start_date": DateFormat('yyyy-MM-dd').format(_startDate!),
        "end_date": DateFormat('yyyy-MM-dd').format(_endDate!),
        "selected_param": _selectedParam,
        "location": "Field",
        "include_chart": true,
        "include_insight": true,
      };

      print("======== API REQUEST ========");
      print(jsonEncode(payload));
      print("================================");

      final response = await http.post(
        Uri.parse(apiUrl),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode(payload),
      );

      print("Status Code: ${response.statusCode}");

      print("======== API RESPONSE START ========");
      const int chunkSize = 800;
      for (int i = 0; i < response.body.length; i += chunkSize) {
        print(
          response.body.substring(
            i,
            i + chunkSize > response.body.length
                ? response.body.length
                : i + chunkSize,
          ),
        );
      }
      print("======== API RESPONSE END ========");

      if (response.statusCode != 200) {
        throw Exception("API Error");
      }

      Map<String, dynamic> body;
      try {
        body = jsonDecode(response.body);
      } catch (e) {
        print("JSON DECODE ERROR: $e");
        setState(() => _loading = false);
        return;
      }

      Uint8List? chartBytes;
      String? insightText;

      if (body["chart"] != null &&
          body["chart"]["image"] != null &&
          body["chart"]["image"] is String) {
        chartBytes = base64Decode(body["chart"]["image"]);
      }

      if (body["ai_insight"] != null &&
          body["ai_insight"]["text"] != null &&
          body["ai_insight"]["text"] is String) {
        insightText = body["ai_insight"]["text"];
      }

      setState(() {
        _chartImage = chartBytes;
        _aiInsight = insightText ?? "No insight available";
        _loading = false;
      });
    } catch (e) {
      print("API ERROR: $e");
      setState(() => _loading = false);
    }
  }

  /// =========================
  /// OPEN FILTER
  /// =========================
  void _openFilterDialog() {
    showDialog(
      context: context,
      builder: (context) {
        return FilterDialog(
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
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.soilHealthHistory),
        backgroundColor: const Color(0xFF1B413C),
      ),
      body: Column(
        children: [
          /// =======================
          /// CHART CONTAINER
          /// =======================
          Padding(
            padding: const EdgeInsets.all(16),
            child: Container(
              height: 220,
              width: double.infinity,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
              ),
              child:
                  _loading
                      ? const Center(child: CircularProgressIndicator())
                      : !_hasSelection
                      ? Center(
                        child: Text(
                          loc.pleaseSelectParameter,
                          style: const TextStyle(
                            fontSize: 16,
                            color: Colors.grey,
                          ),
                        ),
                      )
                      : _chartImage != null
                      ? Image.memory(_chartImage!)
                      : Center(child: Text(loc.noDataAvailable)),
            ),
          ),

          /// =======================
          /// INFO ROW
          /// =======================
          if (_hasSelection)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    _selectedParam ?? "",
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  Text(
                    "${DateFormat('dd MMM').format(_startDate!)} - ${DateFormat('dd MMM').format(_endDate!)}",
                  ),
                ],
              ),
            ),

          const SizedBox(height: 16),

          /// =======================
          /// SUMMARY TITLE
          /// =======================
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(
                loc.summary,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),

          const SizedBox(height: 8),

          /// =======================
          /// SUMMARY CONTENT
          /// =======================
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child:
                  _loading
                      ? const SizedBox()
                      : !_hasSelection
                      ? Center(
                        child: Text(
                          loc.pleaseSelectParameter,
                          style: const TextStyle(color: Colors.grey),
                        ),
                      )
                      : SingleChildScrollView(child: Text(_aiInsight ?? "")),
            ),
          ),

          /// =======================
          /// FILTER BUTTON
          /// =======================
          Padding(
            padding: const EdgeInsets.all(16),
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFFFD358),
                foregroundColor: Colors.black,
                minimumSize: const Size(double.infinity, 50),
              ),
              icon: const Icon(Icons.tune),
              label: Text(loc.filter),
              onPressed: _openFilterDialog,
            ),
          ),
        ],
      ),
    );
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
      initialDate: _startDate!,
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
    );

    if (picked != null) {
      setState(() {
        _startDate = picked;
        _isLastMonth = false;
      });
    }
  }

  Future<void> _pickEndDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _endDate!,
      firstDate: _startDate ?? DateTime(2020),
      lastDate: DateTime.now(),
    );

    if (picked != null) {
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
              /// ======================
              /// SELECT PARAMETER
              /// ======================
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
                      final isSelected = _selectedParam == param;

                      return GestureDetector(
                        onTap: () {
                          setState(() {
                            if (isSelected) {
                              _selectedParam = null;
                            } else {
                              _selectedParam = param;
                            }
                          });
                        },
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 8,
                          ),
                          decoration: BoxDecoration(
                            color:
                                isSelected
                                    ? Colors.white
                                    : Colors.grey.shade100,
                            borderRadius: BorderRadius.circular(24),
                            border: Border.all(
                              color:
                                  isSelected
                                      ? const Color(0xFF1B413C)
                                      : Colors.grey.shade400,
                              width: 1.2,
                            ),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              if (isSelected) ...[
                                const Icon(Icons.close, size: 16),
                                const SizedBox(width: 6),
                              ],
                              Text(
                                param,
                                style: TextStyle(
                                  fontWeight:
                                      isSelected
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

              /// ======================
              /// DATE RANGE
              /// ======================
              Text(
                loc.selectDateRange,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 16),

              /// LAST MONTH PILL
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

              /// CUSTOM
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
                  await _pickEndDate();
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

              /// APPLY BUTTON
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
                      _selectedParam == null
                          ? null
                          : () {
                            widget.onApply(
                              _selectedParam!,
                              _startDate!,
                              _endDate!,
                            );
                          },
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
