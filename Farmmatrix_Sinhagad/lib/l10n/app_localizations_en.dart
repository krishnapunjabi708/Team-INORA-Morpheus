// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get welcomeMessage => 'Welcome to FarmMatrix - Your Smart Farming Solution';

  @override
  String get getStarted => 'Get Started';

  @override
  String get selectLanguage => 'Select Language';

  @override
  String get next => 'Next';

  @override
  String get english => 'English';

  @override
  String get hindi => 'Hindi';

  @override
  String get marathi => 'Marathi';

  @override
  String get tamil => 'Tamil';

  @override
  String get punjabi => 'Punjabi';

  @override
  String get telugu => 'Telugu';

  @override
  String get language => 'Language:';

  @override
  String get farmMatrix => 'FARMMATRIX';

  @override
  String get logIn => 'Log In';

  @override
  String get fullName => 'Full Name';

  @override
  String get loading => 'Loading...';

  @override
  String get currentField => 'Current Field';

  @override
  String get phoneNo => 'Phone Number';

  @override
  String get pleaseEnterName => 'Please enter your name';

  @override
  String get pleaseEnterPhoneNumber => 'Please enter your phone number';

  @override
  String get invalidPhoneNumber => 'Please enter a valid phone number';

  @override
  String get locationServiceDisabledTitle => 'Location Service Disabled';

  @override
  String get locationServiceDisabledMessage => 'Location services are disabled. Please enable them to continue.';

  @override
  String get cancel => 'Cancel';

  @override
  String get openSettings => 'Open Settings';

  @override
  String get locationPermissionRequiredTitle => 'Location Permission Required';

  @override
  String get locationPermissionRequiredMessage => 'We need location permissions to provide better service.';

  @override
  String get locationPermissionPermanentlyDeniedTitle => 'Location Permission Permanently Denied';

  @override
  String get locationPermissionPermanentlyDeniedMessage => 'You have permanently denied location permissions. Please enable them in app settings.';

  @override
  String get locationServicesStillDisabled => 'Location services are still disabled';

  @override
  String get locationServicesRequired => 'Location services are required';

  @override
  String get locationPermissionsStillDenied => 'Location permissions are still denied';

  @override
  String get locationPermissionsPermanentlyDenied => 'Location permissions are permanently denied';

  @override
  String get processing => 'Processing...';

  @override
  String get goodMorning => 'Good Morning';

  @override
  String get goodAfternoon => 'Good Afternoon';

  @override
  String get goodEvening => 'Good Evening';

  @override
  String get loadingUser => 'Loading user...';

  @override
  String welcomeUser(Object name) {
    return 'Welcome, $name';
  }

  @override
  String get defaultUser => 'User';

  @override
  String humidity(Object value) {
    return 'Humidity: $value';
  }

  @override
  String get weather => 'Weather';

  @override
  String get selectField => 'Select Field';

  @override
  String get addNewField => 'Add New Field';

  @override
  String get selectedFieldLabel => 'Selected field: ';

  @override
  String get noFieldSelected => 'No field selected';

  @override
  String get manageFields => 'Manage your fields';

  @override
  String get home => 'Home';

  @override
  String get dashboard => 'Dashboard';

  @override
  String get soilReportTitle => 'Soil Report';

  @override
  String get viewReport => 'View Report';

  @override
  String get onboardingDesc1 => 'A platform designed to help you understand your soil like never before.';

  @override
  String get onboardingDesc2 => 'Delivering clear soil fertility insights for smarter farming decisions.';

  @override
  String get soilReportDescription => 'Get a detailed analysis of soil nutrients and parameters with health score';

  @override
  String get fertilityMappingTitle => 'Fertility Mapping';

  @override
  String get fertilityMappingDescription => 'Get zone-wise fertility map on your selected field';

  @override
  String get viewMap => 'View Map';

  @override
  String get dashboardLabel => 'Dashboard';

  @override
  String get profile => 'Profile';

  @override
  String get ok => 'OK';

  @override
  String get skip => 'Skip';

  @override
  String get changeLanguage => 'Change Language';

  @override
  String get fieldMissing => 'Field data missing';

  @override
  String get apiError => 'API error';

  @override
  String get filterByNutrients => 'Filter by nutrients';

  @override
  String errorGettingLocation(Object message) {
    return 'Error getting location: $message';
  }

  @override
  String get errorFetchingWeather => 'Error fetching weather';

  @override
  String errorGettingAddress(Object message) {
    return 'Error getting address: $message';
  }

  @override
  String get weatherUnavailable => 'Weather unavailable';

  @override
  String get errorLoadingWeather => 'Error loading weather';

  @override
  String get locationServicesDisabled => 'Location services are disabled.';

  @override
  String get locationPermissionsDenied => 'Location permissions are denied.';

  @override
  String error(Object message) {
    return 'Error: $message';
  }

  @override
  String get locationNotFound => 'Location not found.';

  @override
  String searchError(Object message) {
    return 'Search error: $message';
  }

  @override
  String get enterFieldName => 'Enter Field Name';

  @override
  String get enterFieldNameHint => 'Enter field name';

  @override
  String get save => 'Save';

  @override
  String get userIdNotFound => 'User ID not found. Please log in.';

  @override
  String get invalidFieldData => 'Please fill in the field name and draw a valid polygon.';

  @override
  String fieldSavedSuccess(Object fieldName) {
    return 'Field \'$fieldName\' saved successfully!';
  }

  @override
  String get searchLocation => 'Search location...';

  @override
  String get clearField => 'Clear Field';

  @override
  String get clear => 'Clear';

  @override
  String get confirm => 'Confirm';

  @override
  String errorFetchingFields(Object message) {
    return 'Error fetching fields: $message';
  }

  @override
  String get errorLoadingFields => 'Error loading fields';

  @override
  String get retry => 'Retry';

  @override
  String get noFieldsAdded => 'No fields added';

  @override
  String get addFieldPrompt => 'Please add your field to get started';

  @override
  String get pleaseSelectAFieldFirst => 'Please select or add a field first';

  @override
  String get noFieldsSelected => 'No fields selected for deletion';

  @override
  String get fieldsDeletedSuccess => 'Selected fields deleted successfully';

  @override
  String errorDeletingFields(Object message) {
    return 'Error deleting fields: $message';
  }

  @override
  String get deleteSelected => 'Delete Selected';

  @override
  String get fertilityMapping => 'Fertility Mapping';

  @override
  String get loadingFertilityMap => 'Loading fertility map...';

  @override
  String fertilityMapPeriod(Object startDate, Object endDate) {
    return 'Fertility Map: $startDate to $endDate';
  }

  @override
  String get fertilityLow => 'Low';

  @override
  String get fertilityModerate => 'Moderate';

  @override
  String get fertilityHigh => 'High';

  @override
  String get fieldDataMissing => 'Field data or geometry missing';

  @override
  String get invalidGeometry => 'Invalid geometry coordinates';

  @override
  String apiRequestFailed(Object statusCode) {
    return 'API request failed: $statusCode';
  }

  @override
  String errorLoadingData(Object message) {
    return 'Error loading data: $message';
  }

  @override
  String get soilReport => 'Advance Soil Report';

  @override
  String get languageLabel => 'Language:';

  @override
  String get invalidCoordinates => 'Invalid coordinates format';

  @override
  String failedToParseCoordinates(Object message) {
    return 'Failed to parse coordinates: $message';
  }

  @override
  String failedToParseGeometry(Object message) {
    return 'Failed to parse geometry: $message';
  }

  @override
  String get noCoordinatesAvailable => 'No coordinates available';

  @override
  String failedToLoadReport(Object message) {
    return 'Failed to load report: $message';
  }

  @override
  String errorGeneratingReport(Object message) {
    return 'Error generating report: $message';
  }

  @override
  String get noPDFAvailable => 'No PDF available';

  @override
  String get reportDownloadedSuccess => 'Report downloaded successfully';

  @override
  String failedToDownloadReport(Object message) {
    return 'Failed to download report: $message';
  }

  @override
  String errorLoadingPDF(Object message) {
    return 'Error loading PDF: $message';
  }

  @override
  String get downloadReport => 'Download Report';

  @override
  String get soilMonitoringDashboard => 'Soil Monitoring Dashboard';

  @override
  String fieldLabel(Object fieldName) {
    return 'Field: $fieldName';
  }

  @override
  String get noFieldSelectedMessage => 'No field selected or data unavailable. Please select a field from the Home screen.';

  @override
  String get fertilityIndexDefault => 'Fertility Index (Default)';

  @override
  String get nitrogenN => 'Nitrogen (N)';

  @override
  String get phosphorusP => 'Phosphorus (P)';

  @override
  String get potassiumK => 'Potassium (K)';

  @override
  String get organicCarbonOC => 'Organic Carbon (OC)';

  @override
  String get electricalConductivityEC => 'Electrical Conductivity (EC)';

  @override
  String get calciumCa => 'Calcium (Ca)';

  @override
  String get magnesiumMg => 'Magnesium (Mg)';

  @override
  String get sulphurS => 'Sulphur (S)';

  @override
  String get soilPh => 'Soil pH';

  @override
  String get waterContent => 'Water Content';

  @override
  String get organicCarbon => 'Organic Carbon';

  @override
  String get landSurfaceTemperature => 'Land Surface Temperature';

  @override
  String get soilTexture => 'Soil Texture';

  @override
  String get soilSalinity => 'Soil Salinity';

  @override
  String get nutrientsHoldingCapacity => 'Nutrients Holding Capacity';

  @override
  String get nutrientsHoldingCapacityLine1 => 'Nutrients';

  @override
  String get nutrientsHoldingCapacityLine2 => 'Holding';

  @override
  String get nutrientsHoldingCapacityLine3 => 'Capacity';

  @override
  String get nutrientsHoldingCapacityLine4 => ' ';

  @override
  String get insights => 'Insights';

  @override
  String get na => 'N/A';

  @override
  String get dataUnavailable => 'Data unavailable';

  @override
  String get unknown => 'Unknown';

  @override
  String errorFetchingFieldData(Object message) {
    return 'Error fetching field data: $message';
  }

  @override
  String errorFetchingData(Object message) {
    return 'Error fetching data: $message';
  }

  @override
  String get phStatusIdeal => 'Ideal';

  @override
  String get phStatusAcceptable => 'Acceptable';

  @override
  String get phStatusPoor => 'Poor';

  @override
  String get phTooltipIdeal => 'Ideal / Good condition';

  @override
  String get phTooltipMildlyAcidicAlkaline => 'Mildly acidic or alkaline';

  @override
  String get phTooltipCorrectionNeeded => 'Soil correction needed';

  @override
  String get textureLoam => 'Loam';

  @override
  String get textureSandyLoam => 'Sandy Loam';

  @override
  String get textureSiltyLoam => 'Silty Loam';

  @override
  String get textureTooltipGood => 'Good soil texture';

  @override
  String get textureTooltipWorkable => 'Workable, but needs improvement';

  @override
  String get textureTooltipOrganicMatter => 'Add organic matter';

  @override
  String get salinityStatusVeryLow => 'Very Low Salinity';

  @override
  String get salinityStatusLow => 'Low Salinity';

  @override
  String get salinityStatusModerate => 'Moderate Salinity';

  @override
  String get salinityStatusHigh => 'High Salinity';

  @override
  String get salinityStatusVeryHigh => 'Very High Salinity';

  @override
  String get salinityTooltipExcellent => 'Excellent for crops';

  @override
  String get salinityTooltipSuitable => 'Suitable for most crops';

  @override
  String get salinityTooltipMonitor => 'Monitor, may affect sensitive crops';

  @override
  String get salinityTooltipTreatment => 'Needs treatment (gypsum, leaching)';

  @override
  String get salinityTooltipPoor => 'Poor soil, not ideal for farming';

  @override
  String get organicCarbonStatusRich => 'Rich Organic Carbon';

  @override
  String get organicCarbonStatusModerate => 'Moderate Organic Carbon';

  @override
  String get organicCarbonStatusLow => 'Low Organic Carbon';

  @override
  String get organicCarbonStatusWaterBody => 'Water Body';

  @override
  String get organicCarbonTooltipGood => 'Good fertility';

  @override
  String get organicCarbonTooltipCompost => 'Add compost to increase fertility';

  @override
  String get organicCarbonTooltipLow => 'Low fertility';

  @override
  String get cecStatusHigh => 'High';

  @override
  String get cecStatusAverage => 'Average';

  @override
  String get cecStatusLow => 'Low';

  @override
  String get cecTooltipHigh => 'High nutrient holding';

  @override
  String get cecTooltipAverage => 'Average nutrient holding';

  @override
  String get cecTooltipLow => 'Soil lacks holding power';

  @override
  String get lstStatusCool => 'Cool Zone';

  @override
  String get lstStatusOptimal => 'Optimal temperature';

  @override
  String get lstStatusModerate => 'Moderate heat';

  @override
  String get lstStatusHigh => 'High heat stress';

  @override
  String get lstStatusExtreme => 'Extreme stress';

  @override
  String get lstTooltipCool => 'Ideal for most crops; low evapotranspiration';

  @override
  String get lstTooltipOptimal => 'Supports active crop growth';

  @override
  String get lstTooltipModerate => 'May need light irrigation';

  @override
  String get lstTooltipHigh => 'Irrigation required; avoid sowing sensitive crops';

  @override
  String get lstTooltipExtreme => 'Immediate action needed; consider shade or mulching';

  @override
  String get waterContentStatusWaterBody => 'Water body/Lake';

  @override
  String get waterContentStatusAdequate => 'Adequate moisture';

  @override
  String get waterContentStatusMild => 'Mild stress';

  @override
  String get waterContentStatusModerate => 'Moderate stress';

  @override
  String get waterContentStatusDry => 'Dry';

  @override
  String get waterContentTooltipWaterBody => 'It is a water body or a lake';

  @override
  String get waterContentTooltipAdequate => 'Soil/vegetation moisture is adequate—no immediate irrigation needed';

  @override
  String get waterContentTooltipMild => 'Mild moisture stress—consider light irrigation soon';

  @override
  String get waterContentTooltipModerate => 'Moderate stress—plan irrigation within few days';

  @override
  String get waterContentTooltipDry => 'Severe moisture deficit—irrigate immediately';

  @override
  String get account => 'Account';

  @override
  String helloUser(Object name) {
    return 'Hello, $name';
  }

  @override
  String get noPhone => 'No phone';

  @override
  String get myFields => 'My Fields';

  @override
  String get governmentSchemes => 'Government Schemes';

  @override
  String get logout => 'Logout';

  @override
  String get refreshUserData => 'Refresh User Data';

  @override
  String get noUserIdFound => 'No user ID found in SharedPreferences';

  @override
  String errorFetchingUserData(Object message) {
    return 'Error fetching user data: $message';
  }

  @override
  String errorLoggingOut(Object message) {
    return 'Error logging out: $message';
  }

  @override
  String errorDecodingField(Object message) {
    return 'Error decoding saved field: $message';
  }

  @override
  String selectedField(Object fieldName) {
    return 'Selected field: $fieldName';
  }

  @override
  String get pradhanMantriFasalBimaYojana => 'Pradhan Mantri Fasal Bima Yojana';

  @override
  String get kisanCreditCardScheme => 'Kisan Credit Card Scheme';

  @override
  String get paramparagatKrishiVikasYojana => 'Paramparagat Krishi Vikas Yojana';

  @override
  String get yourSelectedField => 'Your Selected Field';

  @override
  String get loadingFieldMap => 'Loading field map...';

  @override
  String get farmMatrixAssistant => 'FarmMatrix Assistant';

  @override
  String get chatHistory => 'Chat History';

  @override
  String get newChat => 'New Chat';

  @override
  String get askYourAssistant => 'Ask your assistant';

  @override
  String get askAnything => 'Ask anything';

  @override
  String get rename => 'Rename';

  @override
  String get delete => 'Delete';

  @override
  String get renameChat => 'Rename Chat';

  @override
  String get enterNewChatName => 'Enter new chat name';

  @override
  String get deleteChat => 'Delete Chat';

  @override
  String get deleteChatConfirmation => 'Are you sure you want to delete this chat? This action cannot be undone.';

  @override
  String get apiErrorMessage => 'Sorry, I couldn\'t process your request. Please try again.';

  @override
  String get soilHealthHistoryTitle => 'Soil Health History';

  @override
  String get soilHealthHistoryDescription => 'Track soil health trends over time';

  @override
  String get viewHistory => 'View History';

  @override
  String get soilHealthHistory => 'Soil Health History';

  @override
  String get selectedParameter => 'Selected Parameter';

  @override
  String get summary => 'Summary';

  @override
  String get filter => 'Filter';

  @override
  String get selectSoilParameter => 'Select Soil Parameter';

  @override
  String get apply => 'Apply';

  @override
  String get noDataAvailable => 'No Data Available';

  @override
  String get pleaseSelectParameter => 'Please select the parameter from filter';

  @override
  String get selectDateRange => 'Select Date Range';

  @override
  String get lastMonth => 'Last month';

  @override
  String get custom => 'Custom';
}
