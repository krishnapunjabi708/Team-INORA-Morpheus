
import 'package:supabase_flutter/supabase_flutter.dart';

class AuthServices {
  static final SupabaseClient _client = Supabase.instance.client;

  // Create user directly and return the user ID
  static Future<String?> createUser({
    required String phone,
    required String fullName,
    required double latitude,
    required double longitude,
  }) async {
    try {
      // Check if user already exists
      final exists = await userExists(phone);
      if (exists) {
        // If user exists, fetch and return their ID
        final response = await _client
            .from('users')
            .select('id')
            .eq('phone_number', phone)
            .single();
        return response['id'] as String?;
      }

      // Insert user data into the database
      final response = await _client.from('users').insert({
        'full_name': fullName,
        'phone_number': phone,
        'latitude': latitude,
        'longitude': longitude,
        'created_at': DateTime.now().toIso8601String(),
        'updated_at': DateTime.now().toIso8601String(),
      }).select('id').single();

      return response['id'] as String?;
    } catch (e) {
      print('Error in createUser: $e');
      rethrow;
    }
  }

  // Check if user exists in the database
  static Future<bool> userExists(String phone) async {
    try {
      final response = await _client
          .from('users')
          .select()
          .eq('phone_number', phone);
      return response.isNotEmpty;
    } catch (e) {
      print('Error checking user existence: $e');
      rethrow;
    }
  }

  // Delete user from the database
  static Future<void> deleteUser(String userId) async {
    try {
      await _client.from('users').delete().eq('id', userId);
    } catch (e) {
      print('Error deleting user: $e');
      rethrow;
    }
  }
}