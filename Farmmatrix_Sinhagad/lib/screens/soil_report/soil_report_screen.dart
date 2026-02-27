import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart' show kDebugMode;
import 'package:path_provider/path_provider.dart';
import 'dart:io';
import 'package:open_file/open_file.dart';
import 'package:farmmatrix/services/field_services.dart';
import 'package:farmmatrix/models/field_info_model.dart';
import 'package:farmmatrix/screens/home/home_screen.dart';
import 'package:flutter_pdfview/flutter_pdfview.dart';
import 'dart:typed_data';
import 'dart:convert';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:farmmatrix/l10n/app_localizations.dart';

class SoilReportScreen extends StatefulWidget {
  final String fieldId;

  const SoilReportScreen({Key? key, required this.fieldId}) : super(key: key);

  @override
  _SoilReportScreenState createState() => _SoilReportScreenState();
}

class _SoilReportScreenState extends State<SoilReportScreen> {
  Uint8List? pdfData;
  String selectedLanguage = 'english';
  bool isLoading = true;
  List<List<double>>? polygonCoordinates;
  final FieldService _fieldService = FieldService();
  String? pdfPath;

  @override
  void initState() {
    super.initState();
    _fetchFieldDataAndGenerateReport();
  }

  Future<void> _fetchFieldDataAndGenerateReport() async {
    try {
      final fieldData = await _fieldService.getFieldData(widget.fieldId);

      if (fieldData == null) {
        throw Exception(AppLocalizations.of(context)!.fieldDataMissing);
      }

      if (fieldData.coordinates != null) {
        polygonCoordinates = _parseCoordinates(fieldData.coordinates!);
      } else if (fieldData.geometry != null) {
        polygonCoordinates = _parseGeometry(fieldData.geometry);
      } else {
        throw Exception(AppLocalizations.of(context)!.noCoordinatesAvailable);
      }

      await _generateSoilReport();
    } catch (e) {
      if (!mounted) return;
      setState(() => isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppLocalizations.of(context)!.error(e.toString())),
        ),
      );
    }
  }

  List<List<double>> _parseCoordinates(dynamic coordinates) {
    try {
      if (coordinates is List) {
        List<List<double>> parsed =
            coordinates.map<List<double>>((coord) {
              // Swap latitude,longitude to longitude,latitude
              return [coord[1].toDouble(), coord[0].toDouble()];
            }).toList();
        // Ensure polygon is closed
        if (parsed.isNotEmpty && (parsed.first != parsed.last)) {
          parsed.add(parsed.first);
        }
        return parsed;
      }
      throw Exception(AppLocalizations.of(context)!.invalidCoordinates);
    } catch (e) {
      throw Exception(
        AppLocalizations.of(context)!.failedToParseCoordinates(e.toString()),
      );
    }
  }

  List<List<double>> _parseGeometry(dynamic geometry) {
    try {
      if (geometry is Map<String, dynamic>) {
        final coordinates = geometry['coordinates'] as List;
        if (coordinates.isNotEmpty && coordinates[0] is List) {
          List<List<double>> parsed =
              coordinates[0].map<List<double>>((coord) {
                // Swap latitude,longitude to longitude,latitude
                return [coord[1].toDouble(), coord[0].toDouble()];
              }).toList();
          // Ensure polygon is closed
          if (parsed.isNotEmpty && (parsed.first != parsed.last)) {
            parsed.add(parsed.first);
          }
          return parsed;
        }
      }
      throw Exception(AppLocalizations.of(context)!.invalidGeometry);
    } catch (e) {
      throw Exception(
        AppLocalizations.of(context)!.failedToParseGeometry(e.toString()),
      );
    }
  }

  String _getApiUrl() {
    switch (selectedLanguage) {
      case 'hindi':
        return "SOIL_REPORT_HINDI_API";
      case 'marathi':
        return "SOIL_REPORT_MARATHI_API";
      case 'tamil':
        return "SOIL_REPORT_TAMIL_API";
      case 'punjabi':
        return "SOIL_REPORT_PUNJABI_API";
      case 'telugu':
        return "SOIL_REPORT_TELUGU_API";
      default:
        return "SOIL_REPORT_ENGLISH_API";
    }
  }

  Future<void> _generateSoilReport() async {
    if (!mounted) return;
    setState(() => isLoading = true);

    try {
      if (polygonCoordinates == null || polygonCoordinates!.isEmpty) {
        throw Exception(AppLocalizations.of(context)!.noCoordinatesAvailable);
      }

      // Close polygon if needed
      if (polygonCoordinates!.first != polygonCoordinates!.last) {
        polygonCoordinates!.add(polygonCoordinates!.first);
      }

      final double lat = polygonCoordinates![0][1];
      final double lon = polygonCoordinates![0][0];

      final requestBody = {
        "lat": lat,
        "lon": lon,
        "start_date": "2024-01-01",
        "end_date": "2024-01-16",
        "buffer_meters": 200,
        "polygon_coords": polygonCoordinates,
        "cec_intercept": 5,
        "cec_slope_clay": 20,
        "cec_slope_om": 15,
      };

      if (kDebugMode) {
        print("API URL: ${_getApiUrl()}");
        print("Request Body: ${jsonEncode(requestBody)}");
      }

      final response = await http.post(
        Uri.parse(_getApiUrl()),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/pdf',
        },
        body: jsonEncode(requestBody),
      );

      if (response.statusCode == 200) {
        final directory = await getApplicationDocumentsDirectory();
        final file = File(
          '${directory.path}/soil_report_${widget.fieldId}_$selectedLanguage.pdf',
        );

        await file.writeAsBytes(response.bodyBytes);

        if (!mounted) return;
        setState(() {
          pdfData = response.bodyBytes;
          pdfPath = file.path;
          isLoading = false;
        });
      } else {
        throw Exception("API returned status ${response.statusCode}");
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            AppLocalizations.of(context)!.errorGeneratingReport(e.toString()),
          ),
        ),
      );
    }
  }

  Future<void> _downloadReport() async {
    try {
      if (pdfPath == null || pdfData == null) {
        throw Exception(AppLocalizations.of(context)!.noPDFAvailable);
      }

      final directory = await getExternalStorageDirectory();
      final file = File(
        '${directory!.path}/soil_report_${widget.fieldId}_$selectedLanguage.pdf',
      );
      await file.writeAsBytes(pdfData!);

      if (kDebugMode) {
        print('Report saved to: ${file.path}');
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppLocalizations.of(context)!.reportDownloadedSuccess),
        ),
      );

      OpenFile.open(file.path);
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            AppLocalizations.of(context)!.failedToDownloadReport(e.toString()),
          ),
        ),
      );
      if (kDebugMode) {
        print('Error downloading report: $e');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;
    return Scaffold(
      appBar: AppBar(
        title: Text(AppLocalizations.of(context)!.soilReport),
        backgroundColor: const Color(0xFF1B413C),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, size: 28),
          onPressed: () {
            Navigator.of(context).pushReplacement(
              MaterialPageRoute(builder: (context) => const HomeScreen()),
            );
          },
        ),
        automaticallyImplyLeading: false,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Text(
                  "${loc.language} ",
                  style: const TextStyle(fontWeight: FontWeight.w500),
                ),
                const SizedBox(width: 8),
                DropdownButton<String>(
                  value: selectedLanguage,
                  underline: const SizedBox(),
                  items: [
                    DropdownMenuItem(
                      value: 'english',
                      child: Text(loc.english),
                    ),
                    DropdownMenuItem(value: 'hindi', child: Text(loc.hindi)),
                    DropdownMenuItem(
                      value: 'marathi',
                      child: Text(loc.marathi),
                    ),
                    DropdownMenuItem(value: 'tamil', child: Text(loc.tamil)),
                    DropdownMenuItem(
                      value: 'punjabi',
                      child: Text(loc.punjabi),
                    ),
                    DropdownMenuItem(value: 'telugu', child: Text(loc.telugu)),
                  ],
                  onChanged: (value) {
                    // value is guaranteed non-null here
                    if (value != selectedLanguage) {
                      setState(() => selectedLanguage = value!);
                      _generateSoilReport();
                    }
                  },
                ),
              ],
            ),
            const SizedBox(height: 16),
            Expanded(
              child:
                  isLoading
                      ? const Center(child: CircularProgressIndicator())
                      : pdfPath != null
                      ? PDFView(
                        filePath: pdfPath!,
                        fitPolicy: FitPolicy.WIDTH,
                        enableSwipe: true,
                        swipeHorizontal: true,
                        autoSpacing: false,
                        pageFling: true,
                      )
                      : Center(
                        child: Text(
                          loc.noPDFAvailable,
                          style: const TextStyle(
                            fontSize: 18,
                            color: Colors.grey,
                          ),
                        ),
                      ),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: pdfPath != null ? _downloadReport : null,
              icon: const Icon(Icons.download),
              label: Text(loc.downloadReport),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF1B413C),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
