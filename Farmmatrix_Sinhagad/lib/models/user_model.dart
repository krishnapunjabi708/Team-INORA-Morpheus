class UserModel {
  final String? id; // Make id nullable
  final String fullName;
  final String phoneNumber;
  final double latitude;
  final double longitude;
  final DateTime createdAt;
  final DateTime updatedAt;

  UserModel({
    this.id, // Make id optional
    required this.fullName,
    required this.phoneNumber,
    required this.latitude,
    required this.longitude,
    required this.createdAt,
    required this.updatedAt,
  });

  // Convert a UserModel into a Map
  Map<String, dynamic> toMap() {
    return {
      'id': id, // Include 'id' in the map
      'full_name': fullName,
      'phone_number': phoneNumber,
      'latitude': latitude,
      'longitude': longitude,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  // Extract a UserModel from a Map
  factory UserModel.fromMap(Map<String, dynamic> map) {
    return UserModel(
      id: map['id'], // Supabase will generate this
      fullName: map['full_name'],
      phoneNumber: map['phone_number'],
      latitude:
          map['latitude']?.toDouble() ?? 0.0, // Ensure latitude is a double
      longitude:
          map['longitude']?.toDouble() ?? 0.0, // Ensure longitude is a double
      createdAt: DateTime.parse(map['created_at']),
      updatedAt: DateTime.parse(map['updated_at']),
    );
  }
}
