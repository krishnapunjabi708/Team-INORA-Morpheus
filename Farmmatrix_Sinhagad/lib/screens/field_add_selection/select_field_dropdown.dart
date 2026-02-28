
// import 'dart:convert';
// import 'package:flutter/material.dart';
// import 'package:supabase_flutter/supabase_flutter.dart';
// import 'package:farmmatrix/models/field_info_model.dart';
// import 'package:farmmatrix/screens/field_add_selection/add_field_screen.dart';
// import 'package:shared_preferences/shared_preferences.dart';
// import 'package:farmmatrix/services/field_services.dart';
// import 'package:farmmatrix/l10n/app_localizations.dart';

// class SelectFieldDropdown extends StatefulWidget {
//   final Function(FieldInfoModel?) onFieldSelected;

//   const SelectFieldDropdown({
//     super.key,
//     required this.onFieldSelected,
//   });

//   @override
//   _SelectFieldDropdownState createState() => _SelectFieldDropdownState();
// }

// class _SelectFieldDropdownState extends State<SelectFieldDropdown> {
//   final SupabaseClient _supabase = Supabase.instance.client;
//   final FieldService _fieldService = FieldService();
//   List<FieldInfoModel> _userFields = [];
//   bool _isLoading = true;
//   bool _hasError = false;
//   String _errorMessage = '';
//   bool _isDeleteMode = false;
//   Set<String> _selectedFieldIds = {};

//   @override
//   void initState() {
//     super.initState();
//     _fetchUserFields();
//   }

//   Future<void> _fetchUserFields() async {
//     try {
//       setState(() {
//         _isLoading = true;
//         _hasError = false;
//       });

//       final prefs = await SharedPreferences.getInstance();
//       final userId = prefs.getString('userId');
//       if (userId == null) {
//         throw Exception(AppLocalizations.of(context)!.userIdNotFound);
//       }

//       final response = await _supabase
//           .from('user_fields')
//           .select()
//           .eq('user_id', userId)
//           .order('created_at', ascending: false);

//       if (response.isEmpty) {
//         setState(() {
//           _userFields = [];
//           _isLoading = false;
//         });
//         return;
//       }

//       setState(() {
//         _userFields = response
//             .map<FieldInfoModel>((field) => FieldInfoModel.fromMap(field))
//             .toList();
//         _isLoading = false;
//       });
//     } catch (e) {
//       setState(() {
//         _hasError = true;
//         _errorMessage = e.toString();
//         _isLoading = false;
//       });
//       ScaffoldMessenger.of(context).showSnackBar(
//         SnackBar(content: Text(AppLocalizations.of(context)!.errorFetchingFields(e.toString()))),
//       );
//     }
//   }

//   Future<void> _handleAddField() async {
//     final result = await Navigator.push<bool>(
//       context,
//       MaterialPageRoute(builder: (context) => const AddFieldScreen()),
//     );

//     if (result == true) {
//       await _fetchUserFields();
//     }
//   }

//   Future<void> _saveSelectedField(FieldInfoModel field) async {
//     final prefs = await SharedPreferences.getInstance();
//     final fieldJson = jsonEncode(field.toMap());
//     await prefs.setString('selectedField', fieldJson);
//   }

//   Future<void> _deleteSelectedFields() async {
//     if (_selectedFieldIds.isEmpty) {
//       ScaffoldMessenger.of(context).showSnackBar(
//         SnackBar(content: Text(AppLocalizations.of(context)!.noFieldsSelected)),
//       );
//       return;
//     }

//     try {
//       final prefs = await SharedPreferences.getInstance();
//       final userId = prefs.getString('userId');
//       if (userId == null) {
//         throw Exception(AppLocalizations.of(context)!.userIdNotFound);
//       }

//       await _fieldService.deleteFields(_selectedFieldIds.toList(), userId);
//       setState(() {
//         _userFields.removeWhere((field) => _selectedFieldIds.contains(field.id));
//         _selectedFieldIds.clear();
//         _isDeleteMode = false;
//       });
//       ScaffoldMessenger.of(context).showSnackBar(
//         SnackBar(content: Text(AppLocalizations.of(context)!.fieldsDeletedSuccess)),
//       );
//     } catch (e) {
//       ScaffoldMessenger.of(context).showSnackBar(
//         SnackBar(content: Text(AppLocalizations.of(context)!.errorDeletingFields(e.toString()))),
//       );
//     }
//   }

//   @override
//   Widget build(BuildContext context) {
//     return Scaffold(
//       appBar: AppBar(
//         title: Text(AppLocalizations.of(context)!.selectField),
//         backgroundColor: const Color(0xFF1B413C),
//         elevation: 0,
//         iconTheme: const IconThemeData(color: Color.fromARGB(255, 255, 255, 255)),
//         actions: [
//           IconButton(
//             icon: const Icon(Icons.delete),
//             onPressed: () {
//               setState(() {
//                 _isDeleteMode = !_isDeleteMode;
//                 if (!_isDeleteMode) {
//                   _selectedFieldIds.clear();
//                 }
//               });
//             },
//           ),
//         ],
//       ),
//       body: _buildBody(),
//       floatingActionButton: _isDeleteMode && _userFields.isNotEmpty
//           ? FloatingActionButton.extended(
//               onPressed: _deleteSelectedFields,
//               label: Text(AppLocalizations.of(context)!.deleteSelected),
//               icon: const Icon(Icons.delete),
//               backgroundColor: Colors.red,
//             )
//           : null,
//     );
//   }

//   Widget _buildBody() {
//     if (_isLoading) {
//       return const Center(child: CircularProgressIndicator());
//     }

//     if (_hasError) {
//       return Center(
//         child: Column(
//           mainAxisAlignment: MainAxisAlignment.center,
//           children: [
//             const Icon(Icons.error_outline, size: 48, color: Colors.red),
//             const SizedBox(height: 16),
//             Text(
//               AppLocalizations.of(context)!.errorLoadingFields,
//               style: TextStyle(
//                 fontSize: 18,
//                 color: Colors.grey[800],
//               ),
//             ),
//             const SizedBox(height: 8),
//             Text(
//               _errorMessage,
//               textAlign: TextAlign.center,
//               style: TextStyle(
//                 fontSize: 14,
//                 color: Colors.grey[600],
//               ),
//             ),
//             const SizedBox(height: 16),
//             ElevatedButton(
//               onPressed: _fetchUserFields,
//               child: Text(AppLocalizations.of(context)!.retry),
//             ),
//           ],
//         ),
//       );
//     }

//     if (_userFields.isEmpty) {
//       return Center(
//         child: Column(
//           mainAxisAlignment: MainAxisAlignment.center,
//           children: [
//             const Icon(Icons.agriculture, size: 48, color: Colors.grey),
//             const SizedBox(height: 16),
//             Text(
//               AppLocalizations.of(context)!.noFieldsAdded,
//               style: const TextStyle(
//                 fontSize: 18,
//                 color: Colors.black54,
//                 fontWeight: FontWeight.bold,
//               ),
//             ),
//             const SizedBox(height: 8),
//             Text(
//               AppLocalizations.of(context)!.addFieldPrompt,
//               style: const TextStyle(
//                 fontSize: 14,
//                 color: Colors.grey,
//               ),
//             ),
//             const SizedBox(height: 20),
//             ElevatedButton(
//               onPressed: _handleAddField,
//               style: ElevatedButton.styleFrom(
//                 backgroundColor: const Color(0xFF116A2A),
//                 padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
//               ),
//               child: Text(AppLocalizations.of(context)!.addNewField),
//             ),
//           ],
//         ),
//       );
//     }

//     return RefreshIndicator(
//       onRefresh: _fetchUserFields,
//       child: ListView.builder(
//         padding: const EdgeInsets.all(16),
//         itemCount: _userFields.length,
//         itemBuilder: (context, index) {
//           final field = _userFields[index];
//           return Card(
//             margin: const EdgeInsets.only(bottom: 16),
//             shape: RoundedRectangleBorder(
//               borderRadius: BorderRadius.circular(10),
//             ),
//             elevation: 2,
//             child: ListTile(
//               contentPadding: const EdgeInsets.symmetric(
//                 horizontal: 16,
//                 vertical: 12,
//               ),
//               title: Text(
//                 field.fieldName,
//                 style: const TextStyle(
//                   fontSize: 16,
//                   fontWeight: FontWeight.w500,
//                 ),
//               ),
//               trailing: _isDeleteMode
//                   ? Checkbox(
//                       value: _selectedFieldIds.contains(field.id),
//                       onChanged: (bool? value) {
//                         setState(() {
//                           if (value == true) {
//                             _selectedFieldIds.add(field.id);
//                           } else {
//                             _selectedFieldIds.remove(field.id);
//                           }
//                         });
//                       },
//                     )
//                   : const Icon(
//                       Icons.arrow_forward,
//                       color: Color(0xFF116A2A),
//                     ),
//               onTap: _isDeleteMode
//                   ? () {
//                       setState(() {
//                         if (_selectedFieldIds.contains(field.id)) {
//                           _selectedFieldIds.remove(field.id);
//                         } else {
//                           _selectedFieldIds.add(field.id);
//                         }
//                       });
//                     }
//                   : () {
//                       widget.onFieldSelected(field);
//                       _saveSelectedField(field);
//                       Navigator.pop(context);
//                     },
//             ),
//           );
//         },
//       ),
//     );
//   }
// }


import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:farmmatrix/models/field_info_model.dart';
import 'package:farmmatrix/screens/field_add_selection/add_field_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:farmmatrix/services/field_services.dart';
import 'package:farmmatrix/l10n/app_localizations.dart';

class SelectFieldDropdown extends StatefulWidget {
  final Function(FieldInfoModel?) onFieldSelected;

  const SelectFieldDropdown({
    super.key,
    required this.onFieldSelected,
  });

  @override
  _SelectFieldDropdownState createState() => _SelectFieldDropdownState();
}

class _SelectFieldDropdownState extends State<SelectFieldDropdown> {
  final SupabaseClient _supabase = Supabase.instance.client;
  final FieldService _fieldService = FieldService();
  List<FieldInfoModel> _userFields = [];
  bool _isLoading = true;
  bool _hasError = false;
  String _errorMessage = '';
  bool _isDeleteMode = false;
  Set<String> _selectedFieldIds = {};

  @override
  void initState() {
    super.initState();
    _fetchUserFields();
  }

  Future<void> _fetchUserFields() async {
    try {
      setState(() {
        _isLoading = true;
        _hasError = false;
      });

      final prefs = await SharedPreferences.getInstance();
      final userId = prefs.getString('userId');
      if (userId == null) {
        throw Exception(AppLocalizations.of(context)!.userIdNotFound);
      }

      final response = await _supabase
          .from('user_fields')
          .select()
          .eq('user_id', userId)
          .order('created_at', ascending: false);

      if (response.isEmpty) {
        setState(() {
          _userFields = [];
          _isLoading = false;
        });
        return;
      }

      setState(() {
        _userFields = response
            .map<FieldInfoModel>((field) => FieldInfoModel.fromMap(field))
            .toList();
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _hasError = true;
        _errorMessage = e.toString();
        _isLoading = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.errorFetchingFields(e.toString()))),
      );
    }
  }

  Future<void> _handleAddField() async {
    final result = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (context) => const AddFieldScreen()),
    );

    if (result == true) {
      await _fetchUserFields();
    }
  }

  Future<void> _saveSelectedField(FieldInfoModel field) async {
    final prefs = await SharedPreferences.getInstance();
    final fieldJson = jsonEncode(field.toMap());
    await prefs.setString('selectedField', fieldJson);
  }

  Future<void> _deleteSelectedFields() async {
    if (_selectedFieldIds.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.noFieldsSelected)),
      );
      return;
    }

    try {
      final prefs = await SharedPreferences.getInstance();
      final userId = prefs.getString('userId');
      if (userId == null) {
        throw Exception(AppLocalizations.of(context)!.userIdNotFound);
      }

      await _fieldService.deleteFields(_selectedFieldIds.toList(), userId);
      setState(() {
        _userFields.removeWhere((field) => _selectedFieldIds.contains(field.id));
        _selectedFieldIds.clear();
        _isDeleteMode = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.fieldsDeletedSuccess)),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context)!.errorDeletingFields(e.toString()))),
      );
    }
  }

  /// Format acres nicely: 32.4 acres, 5.8 acres, 0.0 acres (if null or zero)
  String _formatAcres(double? acres) {
    if (acres == null || acres <= 0) {
      return '0.0 acres';
    }
    // Show 1 decimal place, no trailing zero if whole number
    return acres.toStringAsFixed(1).replaceAll(RegExp(r'\.0$'), '') + ' acres';
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context)!;

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.selectField),
        backgroundColor: const Color(0xFF1B413C),
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete),
            onPressed: () {
              setState(() {
                _isDeleteMode = !_isDeleteMode;
                if (!_isDeleteMode) {
                  _selectedFieldIds.clear();
                }
              });
            },
          ),
        ],
      ),
      body: _buildBody(loc),
      floatingActionButton: _isDeleteMode && _userFields.isNotEmpty
          ? FloatingActionButton.extended(
              onPressed: _deleteSelectedFields,
              label: Text(loc.deleteSelected),
              icon: const Icon(Icons.delete),
              backgroundColor: Colors.red,
            )
          : null,
    );
  }

  Widget _buildBody(AppLocalizations loc) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_hasError) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.red),
            const SizedBox(height: 16),
            Text(
              loc.errorLoadingFields,
              style: TextStyle(fontSize: 18, color: Colors.grey[800]),
            ),
            const SizedBox(height: 8),
            Text(
              _errorMessage,
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 14, color: Colors.grey[600]),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _fetchUserFields,
              child: Text(loc.retry),
            ),
          ],
        ),
      );
    }

    if (_userFields.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.agriculture, size: 48, color: Colors.grey),
            const SizedBox(height: 16),
            Text(
              loc.noFieldsAdded,
              style: const TextStyle(
                fontSize: 18,
                color: Colors.black54,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              loc.addFieldPrompt,
              style: const TextStyle(fontSize: 14, color: Colors.grey),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _handleAddField,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF116A2A),
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
              child: Text(loc.addNewField),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _fetchUserFields,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _userFields.length,
        itemBuilder: (context, index) {
          final field = _userFields[index];
          final acresText = _formatAcres(field.areaInAcres);

          return Card(
            margin: const EdgeInsets.only(bottom: 16),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
            ),
            elevation: 2,
            child: ListTile(
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 16,
                vertical: 12,
              ),
              title: Text(
                '${field.fieldName} ($acresText)',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w500,
                ),
              ),
              trailing: _isDeleteMode
                  ? Checkbox(
                      value: _selectedFieldIds.contains(field.id),
                      onChanged: (bool? value) {
                        setState(() {
                          if (value == true) {
                            _selectedFieldIds.add(field.id);
                          } else {
                            _selectedFieldIds.remove(field.id);
                          }
                        });
                      },
                    )
                  : const Icon(
                      Icons.arrow_forward,
                      color: Color(0xFF116A2A),
                    ),
              onTap: _isDeleteMode
                  ? () {
                      setState(() {
                        if (_selectedFieldIds.contains(field.id)) {
                          _selectedFieldIds.remove(field.id);
                        } else {
                          _selectedFieldIds.add(field.id);
                        }
                      });
                    }
                  : () {
                      widget.onFieldSelected(field);
                      _saveSelectedField(field);
                      Navigator.pop(context);
                    },
            ),
          );
        },
      ),
    );
  }
}