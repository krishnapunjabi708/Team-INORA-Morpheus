import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:farmmatrix/models/field_info_model.dart';

class FieldService {
  final SupabaseClient _supabase = Supabase.instance.client;

  Future<FieldInfoModel?> getFieldData(String fieldId) async {
    try {
      final response = await _supabase
          .from('user_fields')
          .select('id, user_id, field_name, coordinates, geometry, created_at, updated_at')
          .eq('id', fieldId)
          .single();

      return FieldInfoModel.fromMap(response);
    } catch (e) {
      print('Error fetching field data: $e');
      return null;
    }
  }

  Future<void> deleteFields(List<String> fieldIds, String userId) async {
    try {
      await _supabase
          .from('user_fields')
          .delete()
          .eq('user_id', userId)
          .inFilter('id', fieldIds);
    } catch (e) {
      print('Error deleting fields: $e');
      rethrow;
    }
  }
}