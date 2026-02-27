import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_hi.dart';
import 'app_localizations_mr.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale) : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate = _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates = <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('hi'),
    Locale('mr')
  ];

  /// No description provided for @welcomeMessage.
  ///
  /// In en, this message translates to:
  /// **'Welcome to FarmMatrix - Your Smart Farming Solution'**
  String get welcomeMessage;

  /// No description provided for @getStarted.
  ///
  /// In en, this message translates to:
  /// **'Get Started'**
  String get getStarted;

  /// No description provided for @selectLanguage.
  ///
  /// In en, this message translates to:
  /// **'Select Language'**
  String get selectLanguage;

  /// No description provided for @next.
  ///
  /// In en, this message translates to:
  /// **'Next'**
  String get next;

  /// No description provided for @english.
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get english;

  /// No description provided for @hindi.
  ///
  /// In en, this message translates to:
  /// **'Hindi'**
  String get hindi;

  /// No description provided for @marathi.
  ///
  /// In en, this message translates to:
  /// **'Marathi'**
  String get marathi;

  /// No description provided for @tamil.
  ///
  /// In en, this message translates to:
  /// **'Tamil'**
  String get tamil;

  /// No description provided for @punjabi.
  ///
  /// In en, this message translates to:
  /// **'Punjabi'**
  String get punjabi;

  /// No description provided for @telugu.
  ///
  /// In en, this message translates to:
  /// **'Telugu'**
  String get telugu;

  /// No description provided for @language.
  ///
  /// In en, this message translates to:
  /// **'Language:'**
  String get language;

  /// No description provided for @farmMatrix.
  ///
  /// In en, this message translates to:
  /// **'FARMMATRIX'**
  String get farmMatrix;

  /// No description provided for @logIn.
  ///
  /// In en, this message translates to:
  /// **'Log In'**
  String get logIn;

  /// No description provided for @fullName.
  ///
  /// In en, this message translates to:
  /// **'Full Name'**
  String get fullName;

  /// No description provided for @loading.
  ///
  /// In en, this message translates to:
  /// **'Loading...'**
  String get loading;

  /// No description provided for @currentField.
  ///
  /// In en, this message translates to:
  /// **'Current Field'**
  String get currentField;

  /// No description provided for @phoneNo.
  ///
  /// In en, this message translates to:
  /// **'Phone Number'**
  String get phoneNo;

  /// No description provided for @pleaseEnterName.
  ///
  /// In en, this message translates to:
  /// **'Please enter your name'**
  String get pleaseEnterName;

  /// No description provided for @pleaseEnterPhoneNumber.
  ///
  /// In en, this message translates to:
  /// **'Please enter your phone number'**
  String get pleaseEnterPhoneNumber;

  /// No description provided for @invalidPhoneNumber.
  ///
  /// In en, this message translates to:
  /// **'Please enter a valid phone number'**
  String get invalidPhoneNumber;

  /// No description provided for @locationServiceDisabledTitle.
  ///
  /// In en, this message translates to:
  /// **'Location Service Disabled'**
  String get locationServiceDisabledTitle;

  /// No description provided for @locationServiceDisabledMessage.
  ///
  /// In en, this message translates to:
  /// **'Location services are disabled. Please enable them to continue.'**
  String get locationServiceDisabledMessage;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @openSettings.
  ///
  /// In en, this message translates to:
  /// **'Open Settings'**
  String get openSettings;

  /// No description provided for @locationPermissionRequiredTitle.
  ///
  /// In en, this message translates to:
  /// **'Location Permission Required'**
  String get locationPermissionRequiredTitle;

  /// No description provided for @locationPermissionRequiredMessage.
  ///
  /// In en, this message translates to:
  /// **'We need location permissions to provide better service.'**
  String get locationPermissionRequiredMessage;

  /// No description provided for @locationPermissionPermanentlyDeniedTitle.
  ///
  /// In en, this message translates to:
  /// **'Location Permission Permanently Denied'**
  String get locationPermissionPermanentlyDeniedTitle;

  /// No description provided for @locationPermissionPermanentlyDeniedMessage.
  ///
  /// In en, this message translates to:
  /// **'You have permanently denied location permissions. Please enable them in app settings.'**
  String get locationPermissionPermanentlyDeniedMessage;

  /// No description provided for @locationServicesStillDisabled.
  ///
  /// In en, this message translates to:
  /// **'Location services are still disabled'**
  String get locationServicesStillDisabled;

  /// No description provided for @locationServicesRequired.
  ///
  /// In en, this message translates to:
  /// **'Location services are required'**
  String get locationServicesRequired;

  /// No description provided for @locationPermissionsStillDenied.
  ///
  /// In en, this message translates to:
  /// **'Location permissions are still denied'**
  String get locationPermissionsStillDenied;

  /// No description provided for @locationPermissionsPermanentlyDenied.
  ///
  /// In en, this message translates to:
  /// **'Location permissions are permanently denied'**
  String get locationPermissionsPermanentlyDenied;

  /// No description provided for @processing.
  ///
  /// In en, this message translates to:
  /// **'Processing...'**
  String get processing;

  /// No description provided for @goodMorning.
  ///
  /// In en, this message translates to:
  /// **'Good Morning'**
  String get goodMorning;

  /// No description provided for @goodAfternoon.
  ///
  /// In en, this message translates to:
  /// **'Good Afternoon'**
  String get goodAfternoon;

  /// No description provided for @goodEvening.
  ///
  /// In en, this message translates to:
  /// **'Good Evening'**
  String get goodEvening;

  /// No description provided for @loadingUser.
  ///
  /// In en, this message translates to:
  /// **'Loading user...'**
  String get loadingUser;

  /// No description provided for @welcomeUser.
  ///
  /// In en, this message translates to:
  /// **'Welcome, {name}'**
  String welcomeUser(Object name);

  /// No description provided for @defaultUser.
  ///
  /// In en, this message translates to:
  /// **'User'**
  String get defaultUser;

  /// No description provided for @humidity.
  ///
  /// In en, this message translates to:
  /// **'Humidity: {value}'**
  String humidity(Object value);

  /// No description provided for @weather.
  ///
  /// In en, this message translates to:
  /// **'Weather'**
  String get weather;

  /// No description provided for @selectField.
  ///
  /// In en, this message translates to:
  /// **'Select Field'**
  String get selectField;

  /// No description provided for @addNewField.
  ///
  /// In en, this message translates to:
  /// **'Add New Field'**
  String get addNewField;

  /// No description provided for @selectedFieldLabel.
  ///
  /// In en, this message translates to:
  /// **'Selected field: '**
  String get selectedFieldLabel;

  /// No description provided for @noFieldSelected.
  ///
  /// In en, this message translates to:
  /// **'No field selected'**
  String get noFieldSelected;

  /// No description provided for @manageFields.
  ///
  /// In en, this message translates to:
  /// **'Manage your fields'**
  String get manageFields;

  /// No description provided for @home.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get home;

  /// No description provided for @dashboard.
  ///
  /// In en, this message translates to:
  /// **'Dashboard'**
  String get dashboard;

  /// No description provided for @soilReportTitle.
  ///
  /// In en, this message translates to:
  /// **'Soil Report'**
  String get soilReportTitle;

  /// No description provided for @viewReport.
  ///
  /// In en, this message translates to:
  /// **'View Report'**
  String get viewReport;

  /// No description provided for @onboardingDesc1.
  ///
  /// In en, this message translates to:
  /// **'A platform designed to help you understand your soil like never before.'**
  String get onboardingDesc1;

  /// No description provided for @onboardingDesc2.
  ///
  /// In en, this message translates to:
  /// **'Delivering clear soil fertility insights for smarter farming decisions.'**
  String get onboardingDesc2;

  /// No description provided for @soilReportDescription.
  ///
  /// In en, this message translates to:
  /// **'Get a detailed analysis of soil nutrients and parameters with health score'**
  String get soilReportDescription;

  /// No description provided for @fertilityMappingTitle.
  ///
  /// In en, this message translates to:
  /// **'Fertility Mapping'**
  String get fertilityMappingTitle;

  /// No description provided for @fertilityMappingDescription.
  ///
  /// In en, this message translates to:
  /// **'Get zone-wise fertility map on your selected field'**
  String get fertilityMappingDescription;

  /// No description provided for @viewMap.
  ///
  /// In en, this message translates to:
  /// **'View Map'**
  String get viewMap;

  /// No description provided for @dashboardLabel.
  ///
  /// In en, this message translates to:
  /// **'Dashboard'**
  String get dashboardLabel;

  /// No description provided for @profile.
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get profile;

  /// No description provided for @ok.
  ///
  /// In en, this message translates to:
  /// **'OK'**
  String get ok;

  /// No description provided for @skip.
  ///
  /// In en, this message translates to:
  /// **'Skip'**
  String get skip;

  /// No description provided for @changeLanguage.
  ///
  /// In en, this message translates to:
  /// **'Change Language'**
  String get changeLanguage;

  /// No description provided for @fieldMissing.
  ///
  /// In en, this message translates to:
  /// **'Field data missing'**
  String get fieldMissing;

  /// No description provided for @apiError.
  ///
  /// In en, this message translates to:
  /// **'API error'**
  String get apiError;

  /// No description provided for @filterByNutrients.
  ///
  /// In en, this message translates to:
  /// **'Filter by nutrients'**
  String get filterByNutrients;

  /// No description provided for @errorGettingLocation.
  ///
  /// In en, this message translates to:
  /// **'Error getting location: {message}'**
  String errorGettingLocation(Object message);

  /// No description provided for @errorFetchingWeather.
  ///
  /// In en, this message translates to:
  /// **'Error fetching weather'**
  String get errorFetchingWeather;

  /// No description provided for @errorGettingAddress.
  ///
  /// In en, this message translates to:
  /// **'Error getting address: {message}'**
  String errorGettingAddress(Object message);

  /// No description provided for @weatherUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Weather unavailable'**
  String get weatherUnavailable;

  /// No description provided for @errorLoadingWeather.
  ///
  /// In en, this message translates to:
  /// **'Error loading weather'**
  String get errorLoadingWeather;

  /// No description provided for @locationServicesDisabled.
  ///
  /// In en, this message translates to:
  /// **'Location services are disabled.'**
  String get locationServicesDisabled;

  /// No description provided for @locationPermissionsDenied.
  ///
  /// In en, this message translates to:
  /// **'Location permissions are denied.'**
  String get locationPermissionsDenied;

  /// No description provided for @error.
  ///
  /// In en, this message translates to:
  /// **'Error: {message}'**
  String error(Object message);

  /// No description provided for @locationNotFound.
  ///
  /// In en, this message translates to:
  /// **'Location not found.'**
  String get locationNotFound;

  /// No description provided for @searchError.
  ///
  /// In en, this message translates to:
  /// **'Search error: {message}'**
  String searchError(Object message);

  /// No description provided for @enterFieldName.
  ///
  /// In en, this message translates to:
  /// **'Enter Field Name'**
  String get enterFieldName;

  /// No description provided for @enterFieldNameHint.
  ///
  /// In en, this message translates to:
  /// **'Enter field name'**
  String get enterFieldNameHint;

  /// No description provided for @save.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get save;

  /// No description provided for @userIdNotFound.
  ///
  /// In en, this message translates to:
  /// **'User ID not found. Please log in.'**
  String get userIdNotFound;

  /// No description provided for @invalidFieldData.
  ///
  /// In en, this message translates to:
  /// **'Please fill in the field name and draw a valid polygon.'**
  String get invalidFieldData;

  /// No description provided for @fieldSavedSuccess.
  ///
  /// In en, this message translates to:
  /// **'Field \'{fieldName}\' saved successfully!'**
  String fieldSavedSuccess(Object fieldName);

  /// No description provided for @searchLocation.
  ///
  /// In en, this message translates to:
  /// **'Search location...'**
  String get searchLocation;

  /// No description provided for @clearField.
  ///
  /// In en, this message translates to:
  /// **'Clear Field'**
  String get clearField;

  /// No description provided for @clear.
  ///
  /// In en, this message translates to:
  /// **'Clear'**
  String get clear;

  /// No description provided for @confirm.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get confirm;

  /// No description provided for @errorFetchingFields.
  ///
  /// In en, this message translates to:
  /// **'Error fetching fields: {message}'**
  String errorFetchingFields(Object message);

  /// No description provided for @errorLoadingFields.
  ///
  /// In en, this message translates to:
  /// **'Error loading fields'**
  String get errorLoadingFields;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get retry;

  /// No description provided for @noFieldsAdded.
  ///
  /// In en, this message translates to:
  /// **'No fields added'**
  String get noFieldsAdded;

  /// No description provided for @addFieldPrompt.
  ///
  /// In en, this message translates to:
  /// **'Please add your field to get started'**
  String get addFieldPrompt;

  /// No description provided for @pleaseSelectAFieldFirst.
  ///
  /// In en, this message translates to:
  /// **'Please select or add a field first'**
  String get pleaseSelectAFieldFirst;

  /// No description provided for @noFieldsSelected.
  ///
  /// In en, this message translates to:
  /// **'No fields selected for deletion'**
  String get noFieldsSelected;

  /// No description provided for @fieldsDeletedSuccess.
  ///
  /// In en, this message translates to:
  /// **'Selected fields deleted successfully'**
  String get fieldsDeletedSuccess;

  /// No description provided for @errorDeletingFields.
  ///
  /// In en, this message translates to:
  /// **'Error deleting fields: {message}'**
  String errorDeletingFields(Object message);

  /// No description provided for @deleteSelected.
  ///
  /// In en, this message translates to:
  /// **'Delete Selected'**
  String get deleteSelected;

  /// No description provided for @fertilityMapping.
  ///
  /// In en, this message translates to:
  /// **'Fertility Mapping'**
  String get fertilityMapping;

  /// No description provided for @loadingFertilityMap.
  ///
  /// In en, this message translates to:
  /// **'Loading fertility map...'**
  String get loadingFertilityMap;

  /// No description provided for @fertilityMapPeriod.
  ///
  /// In en, this message translates to:
  /// **'Fertility Map: {startDate} to {endDate}'**
  String fertilityMapPeriod(Object startDate, Object endDate);

  /// No description provided for @fertilityLow.
  ///
  /// In en, this message translates to:
  /// **'Low'**
  String get fertilityLow;

  /// No description provided for @fertilityModerate.
  ///
  /// In en, this message translates to:
  /// **'Moderate'**
  String get fertilityModerate;

  /// No description provided for @fertilityHigh.
  ///
  /// In en, this message translates to:
  /// **'High'**
  String get fertilityHigh;

  /// No description provided for @fieldDataMissing.
  ///
  /// In en, this message translates to:
  /// **'Field data or geometry missing'**
  String get fieldDataMissing;

  /// No description provided for @invalidGeometry.
  ///
  /// In en, this message translates to:
  /// **'Invalid geometry coordinates'**
  String get invalidGeometry;

  /// No description provided for @apiRequestFailed.
  ///
  /// In en, this message translates to:
  /// **'API request failed: {statusCode}'**
  String apiRequestFailed(Object statusCode);

  /// No description provided for @errorLoadingData.
  ///
  /// In en, this message translates to:
  /// **'Error loading data: {message}'**
  String errorLoadingData(Object message);

  /// No description provided for @soilReport.
  ///
  /// In en, this message translates to:
  /// **'Advance Soil Report'**
  String get soilReport;

  /// No description provided for @languageLabel.
  ///
  /// In en, this message translates to:
  /// **'Language:'**
  String get languageLabel;

  /// No description provided for @invalidCoordinates.
  ///
  /// In en, this message translates to:
  /// **'Invalid coordinates format'**
  String get invalidCoordinates;

  /// No description provided for @failedToParseCoordinates.
  ///
  /// In en, this message translates to:
  /// **'Failed to parse coordinates: {message}'**
  String failedToParseCoordinates(Object message);

  /// No description provided for @failedToParseGeometry.
  ///
  /// In en, this message translates to:
  /// **'Failed to parse geometry: {message}'**
  String failedToParseGeometry(Object message);

  /// No description provided for @noCoordinatesAvailable.
  ///
  /// In en, this message translates to:
  /// **'No coordinates available'**
  String get noCoordinatesAvailable;

  /// No description provided for @failedToLoadReport.
  ///
  /// In en, this message translates to:
  /// **'Failed to load report: {message}'**
  String failedToLoadReport(Object message);

  /// No description provided for @errorGeneratingReport.
  ///
  /// In en, this message translates to:
  /// **'Error generating report: {message}'**
  String errorGeneratingReport(Object message);

  /// No description provided for @noPDFAvailable.
  ///
  /// In en, this message translates to:
  /// **'No PDF available'**
  String get noPDFAvailable;

  /// No description provided for @reportDownloadedSuccess.
  ///
  /// In en, this message translates to:
  /// **'Report downloaded successfully'**
  String get reportDownloadedSuccess;

  /// No description provided for @failedToDownloadReport.
  ///
  /// In en, this message translates to:
  /// **'Failed to download report: {message}'**
  String failedToDownloadReport(Object message);

  /// No description provided for @errorLoadingPDF.
  ///
  /// In en, this message translates to:
  /// **'Error loading PDF: {message}'**
  String errorLoadingPDF(Object message);

  /// No description provided for @downloadReport.
  ///
  /// In en, this message translates to:
  /// **'Download Report'**
  String get downloadReport;

  /// No description provided for @soilMonitoringDashboard.
  ///
  /// In en, this message translates to:
  /// **'Soil Monitoring Dashboard'**
  String get soilMonitoringDashboard;

  /// No description provided for @fieldLabel.
  ///
  /// In en, this message translates to:
  /// **'Field: {fieldName}'**
  String fieldLabel(Object fieldName);

  /// No description provided for @noFieldSelectedMessage.
  ///
  /// In en, this message translates to:
  /// **'No field selected or data unavailable. Please select a field from the Home screen.'**
  String get noFieldSelectedMessage;

  /// No description provided for @fertilityIndexDefault.
  ///
  /// In en, this message translates to:
  /// **'Fertility Index (Default)'**
  String get fertilityIndexDefault;

  /// No description provided for @nitrogenN.
  ///
  /// In en, this message translates to:
  /// **'Nitrogen (N)'**
  String get nitrogenN;

  /// No description provided for @phosphorusP.
  ///
  /// In en, this message translates to:
  /// **'Phosphorus (P)'**
  String get phosphorusP;

  /// No description provided for @potassiumK.
  ///
  /// In en, this message translates to:
  /// **'Potassium (K)'**
  String get potassiumK;

  /// No description provided for @organicCarbonOC.
  ///
  /// In en, this message translates to:
  /// **'Organic Carbon (OC)'**
  String get organicCarbonOC;

  /// No description provided for @electricalConductivityEC.
  ///
  /// In en, this message translates to:
  /// **'Electrical Conductivity (EC)'**
  String get electricalConductivityEC;

  /// No description provided for @calciumCa.
  ///
  /// In en, this message translates to:
  /// **'Calcium (Ca)'**
  String get calciumCa;

  /// No description provided for @magnesiumMg.
  ///
  /// In en, this message translates to:
  /// **'Magnesium (Mg)'**
  String get magnesiumMg;

  /// No description provided for @sulphurS.
  ///
  /// In en, this message translates to:
  /// **'Sulphur (S)'**
  String get sulphurS;

  /// No description provided for @soilPh.
  ///
  /// In en, this message translates to:
  /// **'Soil pH'**
  String get soilPh;

  /// No description provided for @waterContent.
  ///
  /// In en, this message translates to:
  /// **'Water Content'**
  String get waterContent;

  /// No description provided for @organicCarbon.
  ///
  /// In en, this message translates to:
  /// **'Organic Carbon'**
  String get organicCarbon;

  /// No description provided for @landSurfaceTemperature.
  ///
  /// In en, this message translates to:
  /// **'Land Surface Temperature'**
  String get landSurfaceTemperature;

  /// No description provided for @soilTexture.
  ///
  /// In en, this message translates to:
  /// **'Soil Texture'**
  String get soilTexture;

  /// No description provided for @soilSalinity.
  ///
  /// In en, this message translates to:
  /// **'Soil Salinity'**
  String get soilSalinity;

  /// No description provided for @nutrientsHoldingCapacity.
  ///
  /// In en, this message translates to:
  /// **'Nutrients Holding Capacity'**
  String get nutrientsHoldingCapacity;

  /// No description provided for @nutrientsHoldingCapacityLine1.
  ///
  /// In en, this message translates to:
  /// **'Nutrients'**
  String get nutrientsHoldingCapacityLine1;

  /// No description provided for @nutrientsHoldingCapacityLine2.
  ///
  /// In en, this message translates to:
  /// **'Holding'**
  String get nutrientsHoldingCapacityLine2;

  /// No description provided for @nutrientsHoldingCapacityLine3.
  ///
  /// In en, this message translates to:
  /// **'Capacity'**
  String get nutrientsHoldingCapacityLine3;

  /// No description provided for @nutrientsHoldingCapacityLine4.
  ///
  /// In en, this message translates to:
  /// **' '**
  String get nutrientsHoldingCapacityLine4;

  /// No description provided for @insights.
  ///
  /// In en, this message translates to:
  /// **'Insights'**
  String get insights;

  /// No description provided for @na.
  ///
  /// In en, this message translates to:
  /// **'N/A'**
  String get na;

  /// No description provided for @dataUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Data unavailable'**
  String get dataUnavailable;

  /// No description provided for @unknown.
  ///
  /// In en, this message translates to:
  /// **'Unknown'**
  String get unknown;

  /// No description provided for @errorFetchingFieldData.
  ///
  /// In en, this message translates to:
  /// **'Error fetching field data: {message}'**
  String errorFetchingFieldData(Object message);

  /// No description provided for @errorFetchingData.
  ///
  /// In en, this message translates to:
  /// **'Error fetching data: {message}'**
  String errorFetchingData(Object message);

  /// No description provided for @phStatusIdeal.
  ///
  /// In en, this message translates to:
  /// **'Ideal'**
  String get phStatusIdeal;

  /// No description provided for @phStatusAcceptable.
  ///
  /// In en, this message translates to:
  /// **'Acceptable'**
  String get phStatusAcceptable;

  /// No description provided for @phStatusPoor.
  ///
  /// In en, this message translates to:
  /// **'Poor'**
  String get phStatusPoor;

  /// No description provided for @phTooltipIdeal.
  ///
  /// In en, this message translates to:
  /// **'Ideal / Good condition'**
  String get phTooltipIdeal;

  /// No description provided for @phTooltipMildlyAcidicAlkaline.
  ///
  /// In en, this message translates to:
  /// **'Mildly acidic or alkaline'**
  String get phTooltipMildlyAcidicAlkaline;

  /// No description provided for @phTooltipCorrectionNeeded.
  ///
  /// In en, this message translates to:
  /// **'Soil correction needed'**
  String get phTooltipCorrectionNeeded;

  /// No description provided for @textureLoam.
  ///
  /// In en, this message translates to:
  /// **'Loam'**
  String get textureLoam;

  /// No description provided for @textureSandyLoam.
  ///
  /// In en, this message translates to:
  /// **'Sandy Loam'**
  String get textureSandyLoam;

  /// No description provided for @textureSiltyLoam.
  ///
  /// In en, this message translates to:
  /// **'Silty Loam'**
  String get textureSiltyLoam;

  /// No description provided for @textureTooltipGood.
  ///
  /// In en, this message translates to:
  /// **'Good soil texture'**
  String get textureTooltipGood;

  /// No description provided for @textureTooltipWorkable.
  ///
  /// In en, this message translates to:
  /// **'Workable, but needs improvement'**
  String get textureTooltipWorkable;

  /// No description provided for @textureTooltipOrganicMatter.
  ///
  /// In en, this message translates to:
  /// **'Add organic matter'**
  String get textureTooltipOrganicMatter;

  /// No description provided for @salinityStatusVeryLow.
  ///
  /// In en, this message translates to:
  /// **'Very Low Salinity'**
  String get salinityStatusVeryLow;

  /// No description provided for @salinityStatusLow.
  ///
  /// In en, this message translates to:
  /// **'Low Salinity'**
  String get salinityStatusLow;

  /// No description provided for @salinityStatusModerate.
  ///
  /// In en, this message translates to:
  /// **'Moderate Salinity'**
  String get salinityStatusModerate;

  /// No description provided for @salinityStatusHigh.
  ///
  /// In en, this message translates to:
  /// **'High Salinity'**
  String get salinityStatusHigh;

  /// No description provided for @salinityStatusVeryHigh.
  ///
  /// In en, this message translates to:
  /// **'Very High Salinity'**
  String get salinityStatusVeryHigh;

  /// No description provided for @salinityTooltipExcellent.
  ///
  /// In en, this message translates to:
  /// **'Excellent for crops'**
  String get salinityTooltipExcellent;

  /// No description provided for @salinityTooltipSuitable.
  ///
  /// In en, this message translates to:
  /// **'Suitable for most crops'**
  String get salinityTooltipSuitable;

  /// No description provided for @salinityTooltipMonitor.
  ///
  /// In en, this message translates to:
  /// **'Monitor, may affect sensitive crops'**
  String get salinityTooltipMonitor;

  /// No description provided for @salinityTooltipTreatment.
  ///
  /// In en, this message translates to:
  /// **'Needs treatment (gypsum, leaching)'**
  String get salinityTooltipTreatment;

  /// No description provided for @salinityTooltipPoor.
  ///
  /// In en, this message translates to:
  /// **'Poor soil, not ideal for farming'**
  String get salinityTooltipPoor;

  /// No description provided for @organicCarbonStatusRich.
  ///
  /// In en, this message translates to:
  /// **'Rich Organic Carbon'**
  String get organicCarbonStatusRich;

  /// No description provided for @organicCarbonStatusModerate.
  ///
  /// In en, this message translates to:
  /// **'Moderate Organic Carbon'**
  String get organicCarbonStatusModerate;

  /// No description provided for @organicCarbonStatusLow.
  ///
  /// In en, this message translates to:
  /// **'Low Organic Carbon'**
  String get organicCarbonStatusLow;

  /// No description provided for @organicCarbonStatusWaterBody.
  ///
  /// In en, this message translates to:
  /// **'Water Body'**
  String get organicCarbonStatusWaterBody;

  /// No description provided for @organicCarbonTooltipGood.
  ///
  /// In en, this message translates to:
  /// **'Good fertility'**
  String get organicCarbonTooltipGood;

  /// No description provided for @organicCarbonTooltipCompost.
  ///
  /// In en, this message translates to:
  /// **'Add compost to increase fertility'**
  String get organicCarbonTooltipCompost;

  /// No description provided for @organicCarbonTooltipLow.
  ///
  /// In en, this message translates to:
  /// **'Low fertility'**
  String get organicCarbonTooltipLow;

  /// No description provided for @cecStatusHigh.
  ///
  /// In en, this message translates to:
  /// **'High'**
  String get cecStatusHigh;

  /// No description provided for @cecStatusAverage.
  ///
  /// In en, this message translates to:
  /// **'Average'**
  String get cecStatusAverage;

  /// No description provided for @cecStatusLow.
  ///
  /// In en, this message translates to:
  /// **'Low'**
  String get cecStatusLow;

  /// No description provided for @cecTooltipHigh.
  ///
  /// In en, this message translates to:
  /// **'High nutrient holding'**
  String get cecTooltipHigh;

  /// No description provided for @cecTooltipAverage.
  ///
  /// In en, this message translates to:
  /// **'Average nutrient holding'**
  String get cecTooltipAverage;

  /// No description provided for @cecTooltipLow.
  ///
  /// In en, this message translates to:
  /// **'Soil lacks holding power'**
  String get cecTooltipLow;

  /// No description provided for @lstStatusCool.
  ///
  /// In en, this message translates to:
  /// **'Cool Zone'**
  String get lstStatusCool;

  /// No description provided for @lstStatusOptimal.
  ///
  /// In en, this message translates to:
  /// **'Optimal temperature'**
  String get lstStatusOptimal;

  /// No description provided for @lstStatusModerate.
  ///
  /// In en, this message translates to:
  /// **'Moderate heat'**
  String get lstStatusModerate;

  /// No description provided for @lstStatusHigh.
  ///
  /// In en, this message translates to:
  /// **'High heat stress'**
  String get lstStatusHigh;

  /// No description provided for @lstStatusExtreme.
  ///
  /// In en, this message translates to:
  /// **'Extreme stress'**
  String get lstStatusExtreme;

  /// No description provided for @lstTooltipCool.
  ///
  /// In en, this message translates to:
  /// **'Ideal for most crops; low evapotranspiration'**
  String get lstTooltipCool;

  /// No description provided for @lstTooltipOptimal.
  ///
  /// In en, this message translates to:
  /// **'Supports active crop growth'**
  String get lstTooltipOptimal;

  /// No description provided for @lstTooltipModerate.
  ///
  /// In en, this message translates to:
  /// **'May need light irrigation'**
  String get lstTooltipModerate;

  /// No description provided for @lstTooltipHigh.
  ///
  /// In en, this message translates to:
  /// **'Irrigation required; avoid sowing sensitive crops'**
  String get lstTooltipHigh;

  /// No description provided for @lstTooltipExtreme.
  ///
  /// In en, this message translates to:
  /// **'Immediate action needed; consider shade or mulching'**
  String get lstTooltipExtreme;

  /// No description provided for @waterContentStatusWaterBody.
  ///
  /// In en, this message translates to:
  /// **'Water body/Lake'**
  String get waterContentStatusWaterBody;

  /// No description provided for @waterContentStatusAdequate.
  ///
  /// In en, this message translates to:
  /// **'Adequate moisture'**
  String get waterContentStatusAdequate;

  /// No description provided for @waterContentStatusMild.
  ///
  /// In en, this message translates to:
  /// **'Mild stress'**
  String get waterContentStatusMild;

  /// No description provided for @waterContentStatusModerate.
  ///
  /// In en, this message translates to:
  /// **'Moderate stress'**
  String get waterContentStatusModerate;

  /// No description provided for @waterContentStatusDry.
  ///
  /// In en, this message translates to:
  /// **'Dry'**
  String get waterContentStatusDry;

  /// No description provided for @waterContentTooltipWaterBody.
  ///
  /// In en, this message translates to:
  /// **'It is a water body or a lake'**
  String get waterContentTooltipWaterBody;

  /// No description provided for @waterContentTooltipAdequate.
  ///
  /// In en, this message translates to:
  /// **'Soil/vegetation moisture is adequate—no immediate irrigation needed'**
  String get waterContentTooltipAdequate;

  /// No description provided for @waterContentTooltipMild.
  ///
  /// In en, this message translates to:
  /// **'Mild moisture stress—consider light irrigation soon'**
  String get waterContentTooltipMild;

  /// No description provided for @waterContentTooltipModerate.
  ///
  /// In en, this message translates to:
  /// **'Moderate stress—plan irrigation within few days'**
  String get waterContentTooltipModerate;

  /// No description provided for @waterContentTooltipDry.
  ///
  /// In en, this message translates to:
  /// **'Severe moisture deficit—irrigate immediately'**
  String get waterContentTooltipDry;

  /// No description provided for @account.
  ///
  /// In en, this message translates to:
  /// **'Account'**
  String get account;

  /// No description provided for @helloUser.
  ///
  /// In en, this message translates to:
  /// **'Hello, {name}'**
  String helloUser(Object name);

  /// No description provided for @noPhone.
  ///
  /// In en, this message translates to:
  /// **'No phone'**
  String get noPhone;

  /// No description provided for @myFields.
  ///
  /// In en, this message translates to:
  /// **'My Fields'**
  String get myFields;

  /// No description provided for @governmentSchemes.
  ///
  /// In en, this message translates to:
  /// **'Government Schemes'**
  String get governmentSchemes;

  /// No description provided for @logout.
  ///
  /// In en, this message translates to:
  /// **'Logout'**
  String get logout;

  /// No description provided for @refreshUserData.
  ///
  /// In en, this message translates to:
  /// **'Refresh User Data'**
  String get refreshUserData;

  /// No description provided for @noUserIdFound.
  ///
  /// In en, this message translates to:
  /// **'No user ID found in SharedPreferences'**
  String get noUserIdFound;

  /// No description provided for @errorFetchingUserData.
  ///
  /// In en, this message translates to:
  /// **'Error fetching user data: {message}'**
  String errorFetchingUserData(Object message);

  /// No description provided for @errorLoggingOut.
  ///
  /// In en, this message translates to:
  /// **'Error logging out: {message}'**
  String errorLoggingOut(Object message);

  /// No description provided for @errorDecodingField.
  ///
  /// In en, this message translates to:
  /// **'Error decoding saved field: {message}'**
  String errorDecodingField(Object message);

  /// No description provided for @selectedField.
  ///
  /// In en, this message translates to:
  /// **'Selected field: {fieldName}'**
  String selectedField(Object fieldName);

  /// No description provided for @pradhanMantriFasalBimaYojana.
  ///
  /// In en, this message translates to:
  /// **'Pradhan Mantri Fasal Bima Yojana'**
  String get pradhanMantriFasalBimaYojana;

  /// No description provided for @kisanCreditCardScheme.
  ///
  /// In en, this message translates to:
  /// **'Kisan Credit Card Scheme'**
  String get kisanCreditCardScheme;

  /// No description provided for @paramparagatKrishiVikasYojana.
  ///
  /// In en, this message translates to:
  /// **'Paramparagat Krishi Vikas Yojana'**
  String get paramparagatKrishiVikasYojana;

  /// No description provided for @yourSelectedField.
  ///
  /// In en, this message translates to:
  /// **'Your Selected Field'**
  String get yourSelectedField;

  /// No description provided for @loadingFieldMap.
  ///
  /// In en, this message translates to:
  /// **'Loading field map...'**
  String get loadingFieldMap;

  /// No description provided for @farmMatrixAssistant.
  ///
  /// In en, this message translates to:
  /// **'FarmMatrix Assistant'**
  String get farmMatrixAssistant;

  /// No description provided for @chatHistory.
  ///
  /// In en, this message translates to:
  /// **'Chat History'**
  String get chatHistory;

  /// No description provided for @newChat.
  ///
  /// In en, this message translates to:
  /// **'New Chat'**
  String get newChat;

  /// No description provided for @askYourAssistant.
  ///
  /// In en, this message translates to:
  /// **'Ask your assistant'**
  String get askYourAssistant;

  /// No description provided for @askAnything.
  ///
  /// In en, this message translates to:
  /// **'Ask anything'**
  String get askAnything;

  /// No description provided for @rename.
  ///
  /// In en, this message translates to:
  /// **'Rename'**
  String get rename;

  /// No description provided for @delete.
  ///
  /// In en, this message translates to:
  /// **'Delete'**
  String get delete;

  /// No description provided for @renameChat.
  ///
  /// In en, this message translates to:
  /// **'Rename Chat'**
  String get renameChat;

  /// No description provided for @enterNewChatName.
  ///
  /// In en, this message translates to:
  /// **'Enter new chat name'**
  String get enterNewChatName;

  /// No description provided for @deleteChat.
  ///
  /// In en, this message translates to:
  /// **'Delete Chat'**
  String get deleteChat;

  /// No description provided for @deleteChatConfirmation.
  ///
  /// In en, this message translates to:
  /// **'Are you sure you want to delete this chat? This action cannot be undone.'**
  String get deleteChatConfirmation;

  /// No description provided for @apiErrorMessage.
  ///
  /// In en, this message translates to:
  /// **'Sorry, I couldn\'t process your request. Please try again.'**
  String get apiErrorMessage;
}

class _AppLocalizationsDelegate extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) => <String>['en', 'hi', 'mr'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {


  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en': return AppLocalizationsEn();
    case 'hi': return AppLocalizationsHi();
    case 'mr': return AppLocalizationsMr();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.'
  );
}
