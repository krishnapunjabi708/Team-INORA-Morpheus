// class FieldInfoModel {
//   final String? id; // Make id nullable
//   final String userId;
//   final String fieldName;
//   final Map<String, dynamic> coordinates; // JSON for latitude and longitude
//   final Map<String, dynamic> geometry; // GeoJSON for the drawn area
//   final DateTime createdAt;
//   final DateTime updatedAt;

//   FieldInfoModel({
//     this.id, // Make id optional
//     required this.userId,
//     required this.fieldName,
//     required this.coordinates,
//     required this.geometry,
//     required this.createdAt,
//     required this.updatedAt,
//   });

//   // Convert a FieldInfoModel into a Map
//   Map<String, dynamic> toMap() {
//     return {
//       'id': id, // Include 'id' in the map
//       'user_id': userId,
//       'field_name': fieldName,
//       'coordinates': coordinates,
//       'geometry': geometry,
//       'created_at': createdAt.toIso8601String(),
//       'updated_at': updatedAt.toIso8601String(),
//     };
//   }

//   // Extract a FieldInfoModel from a Map
//   factory FieldInfoModel.fromMap(Map<String, dynamic> map) {
//     return FieldInfoModel(
//       id: map['id'], // Supabase will generate this
//       userId: map['user_id'],
//       fieldName: map['field_name'],
//       coordinates: map['coordinates'] ?? {}, // Default to empty map
//       geometry: map['geometry'] ?? {}, // Default to empty map
//       createdAt: DateTime.parse(map['created_at']),
//       updatedAt: DateTime.parse(map['updated_at']),
//     );
//   }
// }








// class FieldInfoModel {
//   final String id; // Make id non-nullable
//   final String userId;
//   final String fieldName;
//   final List<dynamic> coordinates; // Change to List<dynamic> for coordinates
//   final Map<String, dynamic> geometry; // GeoJSON for the drawn area
//   final DateTime createdAt;
//   final DateTime updatedAt;

//   FieldInfoModel({
//     required this.id, // Make id required
//     required this.userId,
//     required this.fieldName,
//     required this.coordinates,
//     required this.geometry,
//     required this.createdAt,
//     required this.updatedAt,
//   });

//   // Convert a FieldInfoModel into a Map
//   Map<String, dynamic> toMap() {
//     return {
//       'id': id,
//       'user_id': userId,
//       'field_name': fieldName,
//       'coordinates': coordinates,
//       'geometry': geometry,
//       'created_at': createdAt.toIso8601String(),
//       'updated_at': updatedAt.toIso8601String(),
//     };
//   }

//   // Extract a FieldInfoModel from a Map
//   factory FieldInfoModel.fromMap(Map<String, dynamic> map) {
//     return FieldInfoModel(
//       id: map['id'] ?? '', // Ensure id is not null
//       userId: map['user_id'] ?? '',
//       fieldName: map['field_name'] ?? 'Unnamed Field', // Default name
//       coordinates: map['coordinates'] ?? [], // Default to empty list
//       geometry: map['geometry'] ?? {}, // Default to empty map
//       createdAt: DateTime.parse(map['created_at'] ?? DateTime.now().toIso8601String()),
//       updatedAt: DateTime.parse(map['updated_at'] ?? DateTime.now().toIso8601String()),
//     );
//   }
// }



class FieldInfoModel {
  final String id;
  final String userId;
  final String fieldName;
  final List<dynamic> coordinates;
  final Map<String, dynamic> geometry;
  final DateTime createdAt;
  final DateTime updatedAt;

  FieldInfoModel({
    required this.id,
    required this.userId,
    required this.fieldName,
    required this.coordinates,
    required this.geometry,
    required this.createdAt,
    required this.updatedAt,
  });

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'user_id': userId,
      'field_name': fieldName,
      'coordinates': coordinates,
      'geometry': geometry,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  factory FieldInfoModel.fromMap(Map<String, dynamic> map) {
    return FieldInfoModel(
      id: map['id'] ?? '',
      userId: map['user_id'] ?? '',
      fieldName: map['field_name'] ?? 'Unnamed Field',
      coordinates: map['coordinates'] ?? [],
      geometry: map['geometry'] ?? {},
      createdAt: DateTime.parse(map['created_at'] ?? DateTime.now().toIso8601String()),
      updatedAt: DateTime.parse(map['updated_at'] ?? DateTime.now().toIso8601String()),
    );
  }
}