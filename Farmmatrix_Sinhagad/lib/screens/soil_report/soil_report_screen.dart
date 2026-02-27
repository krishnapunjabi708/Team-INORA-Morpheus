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
  String selectedLanguage = 'english'; // Default to English
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
        // Fallback to required coordinates for testing
        polygonCoordinates = [
          [73.9880876, 18.4714251],
          [73.9886227, 18.4713949],
          [73.9885851, 18.4708559],
          [73.9880634, 18.4708365],
          [73.9880876, 18.4714251],
        ];
        if (kDebugMode) {
          print('Using fallback coordinates due to missing Supabase data');
        }
      }

      await _generateSoilReport();
    } catch (e) {
      setState(() {
        isLoading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            AppLocalizations.of(context)!.failedToLoadReport(e.toString()),
          ),
        ),
      );
      if (kDebugMode) {
        print('Error: $e');
      }
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

  Future<void> _generateSoilReport() async {
    setState(() {
      isLoading = true;
    });

    try {
      if (polygonCoordinates == null || polygonCoordinates!.isEmpty) {
        throw Exception(AppLocalizations.of(context)!.noCoordinatesAvailable);
      }

      // Validate polygon is closed
      if (polygonCoordinates!.first != polygonCoordinates!.last) {
        polygonCoordinates!.add(polygonCoordinates!.first);
      }

      if (kDebugMode) {
        print(
          'Request payload: ${json.encode({"polygon": polygonCoordinates, "language": selectedLanguage})}',
        );
      }

      // Select API endpoint based on language
      final apiUrl =
          selectedLanguage == 'hindi'
              ? dotenv.env['SOIL_REPORT_HINDI_API']
              : dotenv.env['SOIL_REPORT_ENGLISH_API'];

      if (apiUrl == null) {
        throw Exception("API URL not found");
      }
      final response = await http.post(
        Uri.parse(apiUrl),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/pdf',
        },
        body: json.encode({
          "polygon": polygonCoordinates,
          "language": selectedLanguage,
        }),
      );

      if (kDebugMode) {
        print('API Response Status Code: ${response.statusCode}');
        print('API Response Headers: ${response.headers}');
        if (response.bodyBytes.isNotEmpty) {
          try {
            final responseBody = utf8.decode(
              response.bodyBytes,
              allowMalformed: true,
            );
            print('API Response Body (as string): $responseBody');
          } catch (e) {
            print(
              'API Response Body is binary (likely PDF or corrupted): ${response.bodyBytes.length} bytes',
            );
          }
        } else {
          print('API Response Body: Empty');
        }
      }

      if (response.statusCode == 200) {
        final directory = await getApplicationDocumentsDirectory();
        final file = File(
          '${directory.path}/soil_report_${widget.fieldId}_$selectedLanguage.pdf',
        );
        await file.writeAsBytes(response.bodyBytes);

        setState(() {
          pdfData = response.bodyBytes;
          pdfPath = file.path;
          isLoading = false;
        });
      } else {
        throw Exception(
          AppLocalizations.of(
            context,
          )!.failedToLoadReport(response.statusCode.toString()),
        );
      }
    } catch (e) {
      setState(() {
        isLoading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            AppLocalizations.of(context)!.errorGeneratingReport(e.toString()),
          ),
        ),
      );
      if (kDebugMode) {
        print('Error generating report: $e');
      }
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
    return Scaffold(
      appBar: AppBar(
        title: Text(AppLocalizations.of(context)!.soilReport),
        backgroundColor: const Color(0xFF178D38),
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
        padding: const EdgeInsets.all(8.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Text(AppLocalizations.of(context)!.languageLabel),
                const SizedBox(width: 8),
                DropdownButton<String>(
                  value: selectedLanguage,
                  items: [
                    DropdownMenuItem(
                      value: 'english',
                      child: Text(AppLocalizations.of(context)!.english),
                    ),
                    DropdownMenuItem(
                      value: 'hindi',
                      child: Text(AppLocalizations.of(context)!.hindi),
                    ),
                  ],
                  onChanged: (String? newValue) {
                    if (newValue != null) {
                      setState(() {
                        selectedLanguage = newValue;
                      });
                      _generateSoilReport();
                    }
                  },
                  style: const TextStyle(fontSize: 17, color: Colors.black),
                  dropdownColor: Colors.white,
                  icon: const Icon(Icons.arrow_drop_down, size: 28),
                ),
              ],
            ),
            const SizedBox(height: 32),
            Expanded(
              child:
                  isLoading
                      ? const Center(child: CircularProgressIndicator())
                      : pdfData != null && pdfPath != null
                      ? Container(
                        padding: const EdgeInsets.symmetric(vertical: 10.0),
                        child: Transform.scale(
                          scale: 1.2,
                          child: PDFView(
                            filePath: pdfPath!,
                            enableSwipe: true,
                            swipeHorizontal: false,
                            autoSpacing: true,
                            pageFling: true,
                            fitPolicy: FitPolicy.WIDTH,
                            onError: (error) {
                              if (kDebugMode) {
                                print('PDFView error: $error');
                              }
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(
                                    AppLocalizations.of(
                                      context,
                                    )!.errorLoadingPDF(error.toString()),
                                  ),
                                ),
                              );
                            },
                          ),
                        ),
                      )
                      : Center(
                        child: Text(
                          AppLocalizations.of(context)!.noPDFAvailable,
                        ),
                      ),
            ),
            const SizedBox(height: 20),
            Center(
              child: ElevatedButton(
                onPressed: _downloadReport,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF178D38),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 35,
                    vertical: 10,
                  ),
                ),
                child: Text(AppLocalizations.of(context)!.downloadReport),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
