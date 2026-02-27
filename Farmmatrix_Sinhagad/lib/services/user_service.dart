import 'package:farmmatrix/models/user_model.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class UserService {
  final SupabaseClient _client = Supabase.instance.client;

  // Get user data by user ID
  Future<UserModel> getUserData(String userId) async {
    try {
      final response = await _client
          .from('users')
          .select()
          .eq('id', userId)
          .single();

      return UserModel.fromMap(response);
    } catch (e) {
      throw Exception('Failed to get user data: $e');
    }
  }

  // Get current logged-in user data
  Future<UserModel?> getCurrentUserData() async {
    try {
      final user = _client.auth.currentUser;
      if (user == null) return null;

      final response = await _client
          .from('users')
          .select()
          .eq('id', user.id)
          .single();

      return UserModel.fromMap(response);
    } catch (e) {
      print('Error getting current user data: $e');
      return null;
    }
  }

  // Update user data
  Future<void> updateUserData({
    required String userId,
    String? fullName,
    String? phoneNumber,
    double? latitude,
    double? longitude,
  }) async {
    try {
      final updateData = <String, dynamic>{
        'updated_at': DateTime.now().toIso8601String(),
      };

      if (fullName != null) updateData['full_name'] = fullName;
      if (phoneNumber != null) updateData['phone_number'] = phoneNumber;
      if (latitude != null) updateData['latitude'] = latitude;
      if (longitude != null) updateData['longitude'] = longitude;

      await _client
          .from('users')
          .update(updateData)
          .eq('id', userId);
    } catch (e) {
      throw Exception('Failed to update user data: $e');
    }
  }
}