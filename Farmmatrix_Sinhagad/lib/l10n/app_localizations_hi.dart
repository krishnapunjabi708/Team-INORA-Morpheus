// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Hindi (`hi`).
class AppLocalizationsHi extends AppLocalizations {
  AppLocalizationsHi([String locale = 'hi']) : super(locale);

  @override
  String get welcomeMessage => 'फार्ममैट्रिक्स में स्वागत है - आपका आसान खेती समाधान';

  @override
  String get getStarted => 'शुरू करें';

  @override
  String get selectLanguage => 'भाषा चुनें';

  @override
  String get next => 'आगे';

  @override
  String get english => 'अंग्रेजी';

  @override
  String get hindi => 'हिन्दी';

  @override
  String get marathi => 'मराठी';

  @override
  String get tamil => 'तमिल';

  @override
  String get punjabi => 'पंजाबी';

  @override
  String get telugu => 'तेलुगु';

  @override
  String get language => 'भाषा:';

  @override
  String get farmMatrix => 'फार्ममैट्रिक्स';

  @override
  String get logIn => 'लॉगिन करें';

  @override
  String get fullName => 'पूरा नाम';

  @override
  String get loading => 'लोड हो रहा है...';

  @override
  String get currentField => 'वर्तमान खेत';

  @override
  String get phoneNo => 'फोन नंबर';

  @override
  String get pleaseEnterName => 'अपना नाम डालें';

  @override
  String get pleaseEnterPhoneNumber => 'अपना फोन नंबर डालें';

  @override
  String get invalidPhoneNumber => 'सही फोन नंबर डालें';

  @override
  String get locationServiceDisabledTitle => 'जगह की सेवा बंद है';

  @override
  String get locationServiceDisabledMessage => 'जगह की सेवा बंद है। कृपया इसे चालू करें।';

  @override
  String get cancel => 'रद्द करें';

  @override
  String get openSettings => 'सेटिंग्स खोलें';

  @override
  String get locationPermissionRequiredTitle => 'जगह की अनुमति चाहिए';

  @override
  String get locationPermissionRequiredMessage => 'बेहतर सेवा के लिए हमें जगह की अनुमति चाहिए।';

  @override
  String get locationPermissionPermanentlyDeniedTitle => 'जगह की अनुमति हमेशा के लिए बंद';

  @override
  String get locationPermissionPermanentlyDeniedMessage => 'आपने जगह की अनुमति पूरी तरह से बंद कर दी है। कृपया ऐप सेटिंग्स में इसे चालू करें।';

  @override
  String get locationServicesStillDisabled => 'जगह की सेवा अभी भी बंद है';

  @override
  String get locationServicesRequired => 'जगह की सेवा जरूरी है';

  @override
  String get locationPermissionsStillDenied => 'जगह की अनुमति अभी भी बंद है';

  @override
  String get locationPermissionsPermanentlyDenied => 'जगह की अनुमति हमेशा के लिए बंद है';

  @override
  String get processing => 'काम चल रहा है...';

  @override
  String get goodMorning => 'सुप्रभात';

  @override
  String get goodAfternoon => 'शुभ दोपहर';

  @override
  String get goodEvening => 'शुभ संध्या';

  @override
  String get loadingUser => 'उपयोगकर्ता लोड हो रहा है...';

  @override
  String welcomeUser(Object name) {
    return 'नमस्ते, $name';
  }

  @override
  String get defaultUser => 'उपयोगकर्ता';

  @override
  String humidity(Object value) {
    return 'नमी: $value';
  }

  @override
  String get weather => 'मौसम';

  @override
  String get selectField => 'खेत चुनें';

  @override
  String get addNewField => 'नया खेत जोड़ें';

  @override
  String get selectedFieldLabel => 'चुना हुआ खेत: ';

  @override
  String get noFieldSelected => 'कोई खेत नहीं चुना';

  @override
  String get manageFields => 'अपने खेतों का प्रबंधन करें';

  @override
  String get home => 'होम';

  @override
  String get dashboard => 'डैशबोर्ड';

  @override
  String get soilReportTitle => 'मृदा रिपोर्ट';

  @override
  String get viewReport => 'View Report';

  @override
  String get onboardingDesc1 => 'एक ऐसा प्लेटफॉर्म जो आपको अपनी मिट्टी को पहले से बेहतर समझने में मदद करता है।';

  @override
  String get onboardingDesc2 => 'स्मार्ट खेती के लिए स्पष्ट मिट्टी उर्वरता जानकारी प्रदान करता है।';

  @override
  String get soilReportDescription => 'मृदा पोषक तत्वों और पैरामीटरों का विस्तृत विश्लेषण प्राप्त करें जिसमें स्वास्थ्य स्कोर शामिल है';

  @override
  String get fertilityMappingTitle => 'उर्वरता मानचित्रण';

  @override
  String get fertilityMappingDescription => 'अपने चयनित खेत पर क्षेत्र-वार उर्वरता मानचित्र प्राप्त करें';

  @override
  String get viewMap => 'मानचित्र देखें';

  @override
  String get dashboardLabel => 'डैशबोर्ड';

  @override
  String get profile => 'प्रोफाइल';

  @override
  String get ok => 'ठीक है';

  @override
  String get skip => 'छोड़ें';

  @override
  String errorGettingLocation(Object message) {
    return 'जगह ढूंढने में गलती: $message';
  }

  @override
  String get errorFetchingWeather => 'मौसम जानने में गलती';

  @override
  String errorGettingAddress(Object message) {
    return 'पता ढूंढने में गलती: $message';
  }

  @override
  String get weatherUnavailable => 'मौसम की जानकारी नहीं है';

  @override
  String get errorLoadingWeather => 'मौसम लोड करने में गलती';

  @override
  String get locationServicesDisabled => 'जगह की सेवा बंद है।';

  @override
  String get locationPermissionsDenied => 'जगह की अनुमति नहीं दी गई।';

  @override
  String error(Object message) {
    return 'गलती: $message';
  }

  @override
  String get locationNotFound => 'जगह नहीं मिली।';

  @override
  String searchError(Object message) {
    return 'खोज में गलती: $message';
  }

  @override
  String get enterFieldName => 'खेत का नाम डालें';

  @override
  String get enterFieldNameHint => 'खेत का नाम डालें';

  @override
  String get save => 'सहेजें';

  @override
  String get userIdNotFound => 'उपयोगकर्ता आईडी नहीं मिली। कृपया लॉगिन करें।';

  @override
  String get invalidFieldData => 'खेत का नाम और सही आकार डालें।';

  @override
  String fieldSavedSuccess(Object fieldName) {
    return 'खेत \'$fieldName\' सफलतापूर्वक सहेजा गया!';
  }

  @override
  String get searchLocation => 'जगह खोजें...';

  @override
  String get clearField => 'खेत साफ करें';

  @override
  String get clear => 'साफ करें';

  @override
  String get confirm => 'पक्का करें';

  @override
  String errorFetchingFields(Object message) {
    return 'खेत की जानकारी लेने में गलती: $message';
  }

  @override
  String get errorLoadingFields => 'खेत लोड करने में गलती';

  @override
  String get retry => 'फिर से कोशिश करें';

  @override
  String get noFieldsAdded => 'कोई खेत नहीं जोड़ा गया';

  @override
  String get addFieldPrompt => 'शुरू करने के लिए खेत जोड़ें';

  @override
  String get pleaseSelectAFieldFirst => 'कृपया पहले कोई खेत चुनें या जोड़ें';

  @override
  String get noFieldsSelected => 'हटाने के लिए कोई खेत नहीं चुना';

  @override
  String get fieldsDeletedSuccess => 'चुने हुए खेत हटा दिए गए';

  @override
  String errorDeletingFields(Object message) {
    return 'खेत हटाने में गलती: $message';
  }

  @override
  String get deleteSelected => 'चुने हुए हटाएँ';

  @override
  String get fertilityMapping => 'उर्वरता नक्शा';

  @override
  String get loadingFertilityMap => 'उर्वरता नक्शा लोड हो रहा है...';

  @override
  String fertilityMapPeriod(Object startDate, Object endDate) {
    return 'उर्वरता नक्शा: $startDate से $endDate तक';
  }

  @override
  String get fertilityLow => 'कम';

  @override
  String get fertilityModerate => 'मध्यम';

  @override
  String get fertilityHigh => 'ज्यादा';

  @override
  String get fieldDataMissing => 'खेत की जानकारी या आकार गायब है';

  @override
  String get invalidGeometry => 'गलत आकार के निर्देशांक';

  @override
  String apiRequestFailed(Object statusCode) {
    return 'API अनुरोध विफल: $statusCode';
  }

  @override
  String errorLoadingData(Object message) {
    return 'डेटा लोड करने में गलती: $message';
  }

  @override
  String get soilReport => 'मिट्टी की रिपोर्ट';

  @override
  String get languageLabel => 'भाषा:';

  @override
  String get invalidCoordinates => 'गलत निर्देशांक';

  @override
  String failedToParseCoordinates(Object message) {
    return 'निर्देशांक समझने में गलती: $message';
  }

  @override
  String failedToParseGeometry(Object message) {
    return 'आकार समझने में गलती: $message';
  }

  @override
  String get noCoordinatesAvailable => 'कोई निर्देशांक नहीं हैं';

  @override
  String failedToLoadReport(Object message) {
    return 'रिपोर्ट लोड करने में गलती: $message';
  }

  @override
  String errorGeneratingReport(Object message) {
    return 'रिपोर्ट बनाने में गलती: $message';
  }

  @override
  String get noPDFAvailable => 'कोई PDF नहीं है';

  @override
  String get reportDownloadedSuccess => 'रिपोर्ट सफलतापूर्वक डाउनलोड हुई';

  @override
  String failedToDownloadReport(Object message) {
    return 'रिपोर्ट डाउनलोड करने में गलती: $message';
  }

  @override
  String errorLoadingPDF(Object message) {
    return 'PDF लोड करने में गलती: $message';
  }

  @override
  String get downloadReport => 'रिपोर्ट डाउनलोड करें';

  @override
  String get soilMonitoringDashboard => 'मिट्टी निगरानी डैशबोर्ड';

  @override
  String fieldLabel(Object fieldName) {
    return 'खेत: $fieldName';
  }

  @override
  String get noFieldSelectedMessage => 'कोई खेत नहीं चुना गया या डेटा नहीं है। कृपया होम स्क्रीन से खेत चुनें।';

  @override
  String get soilPh => 'मिट्टी का पीएच';

  @override
  String get waterContent => 'पानी की मात्रा';

  @override
  String get organicCarbon => 'जैविक कार्बन';

  @override
  String get landSurfaceTemperature => 'जमीन का तापमान';

  @override
  String get soilTexture => 'मिट्टी की बनावट';

  @override
  String get soilSalinity => 'मिट्टी की नमकीनता';

  @override
  String get nutrientsHoldingCapacity => 'पोषक तत्व रखने की क्षमता';

  @override
  String get nutrientsHoldingCapacityLine1 => 'पोषक तत्व';

  @override
  String get nutrientsHoldingCapacityLine2 => 'रखने';

  @override
  String get nutrientsHoldingCapacityLine3 => 'की';

  @override
  String get nutrientsHoldingCapacityLine4 => 'क्षमता';

  @override
  String get insights => 'जानकारी';

  @override
  String get na => 'नहीं है';

  @override
  String get dataUnavailable => 'डेटा नहीं है';

  @override
  String get unknown => 'पता नहीं';

  @override
  String errorFetchingFieldData(Object message) {
    return 'खेत का डेटा लेने में गलती: $message';
  }

  @override
  String errorFetchingData(Object message) {
    return 'डेटा लेने में गलती: $message';
  }

  @override
  String get phStatusIdeal => 'उत्तम';

  @override
  String get phStatusAcceptable => 'ठीक';

  @override
  String get phStatusPoor => 'खराब';

  @override
  String get phTooltipIdeal => 'उत्तम / अच्छी स्थिति';

  @override
  String get phTooltipMildlyAcidicAlkaline => 'हल्का अम्लीय या क्षारीय';

  @override
  String get phTooltipCorrectionNeeded => 'मिट्टी को सुधारने की जरूरत';

  @override
  String get textureLoam => 'दोमट';

  @override
  String get textureSandyLoam => 'बलुई दोमट';

  @override
  String get textureSiltyLoam => 'गाद दोमट';

  @override
  String get textureTooltipGood => 'अच्छी मिट्टी की बनावट';

  @override
  String get textureTooltipWorkable => 'काम करने लायक, लेकिन सुधार चाहिए';

  @override
  String get textureTooltipOrganicMatter => 'जैविक खाद डालें';

  @override
  String get salinityStatusVeryLow => 'बहुत कम नमकीनता';

  @override
  String get salinityStatusLow => 'कम नमकीनता';

  @override
  String get salinityStatusModerate => 'मध्यम नमकीनता';

  @override
  String get salinityStatusHigh => 'ज्यादा नमकीनता';

  @override
  String get salinityStatusVeryHigh => 'बहुत ज्यादा नमकीनता';

  @override
  String get salinityTooltipExcellent => 'फसलों के लिए बहुत अच्छा';

  @override
  String get salinityTooltipSuitable => 'ज्यादातर फसलों के लिए ठीक';

  @override
  String get salinityTooltipMonitor => 'नजर रखें, संवेदनशील फसलों पर असर हो सकता है';

  @override
  String get salinityTooltipTreatment => 'इलाज चाहिए (जिप्सम, पानी से धोना)';

  @override
  String get salinityTooltipPoor => 'खराब मिट्टी, खेती के लिए अच्छी नहीं';

  @override
  String get organicCarbonStatusRich => 'ज्यादा जैविक कार्बन';

  @override
  String get organicCarbonStatusModerate => 'मध्यम जैविक कार्बन';

  @override
  String get organicCarbonStatusLow => 'कम जैविक कार्बन';

  @override
  String get organicCarbonStatusWaterBody => 'पानी का क्षेत्र';

  @override
  String get organicCarbonTooltipGood => 'अच्छी उर्वरता';

  @override
  String get organicCarbonTooltipCompost => 'उर्वरता बढ़ाने के लिए खाद डालें';

  @override
  String get organicCarbonTooltipLow => 'कम उर्वरता';

  @override
  String get cecStatusHigh => 'ज्यादा';

  @override
  String get cecStatusAverage => 'मध्यम';

  @override
  String get cecStatusLow => 'कम';

  @override
  String get cecTooltipHigh => 'ज्यादा पोषक तत्व रखने की क्षमता';

  @override
  String get cecTooltipAverage => 'मध्यम पोषक तत्व रखने की क्षमता';

  @override
  String get cecTooltipLow => 'मिट्टी में पोषक तत्व रखने की कमी';

  @override
  String get lstStatusCool => 'ठंडा क्षेत्र';

  @override
  String get lstStatusOptimal => 'सही तापमान';

  @override
  String get lstStatusModerate => 'मध्यम गर्मी';

  @override
  String get lstStatusHigh => 'ज्यादा गर्मी का तनाव';

  @override
  String get lstStatusExtreme => 'बहुत ज्यादा तनाव';

  @override
  String get lstTooltipCool => 'ज्यादातर फसलों के लिए अच्छा; कम पानी का नुकसान';

  @override
  String get lstTooltipOptimal => 'फसलों की वृद्धि के लिए ठीक';

  @override
  String get lstTooltipModerate => 'हल्की सिंचाई की जरूरत हो सकती है';

  @override
  String get lstTooltipHigh => 'सिंचाई जरूरी; संवेदनशील फसलों से बचें';

  @override
  String get lstTooltipExtreme => 'तुरंत कार्रवाई करें; छाया या मल्चिंग करें';

  @override
  String get waterContentStatusWaterBody => 'पानी का क्षेत्र/झील';

  @override
  String get waterContentStatusAdequate => 'पर्याप्त नमी';

  @override
  String get waterContentStatusMild => 'हल्की नमी की कमी';

  @override
  String get waterContentStatusModerate => 'मध्यम नमी की कमी';

  @override
  String get waterContentStatusDry => 'सूखा';

  @override
  String get waterContentTooltipWaterBody => 'यह पानी का क्षेत्र या झील है';

  @override
  String get waterContentTooltipAdequate => 'मिट्टी/पौधों में नमी ठीक है—सिंचाई की जरूरत नहीं';

  @override
  String get waterContentTooltipMild => 'हल्की नमी की कमी—जल्दी हल्की सिंचाई करें';

  @override
  String get waterContentTooltipModerate => 'मध्यम नमी की कमी—कुछ दिनों में सिंचाई करें';

  @override
  String get waterContentTooltipDry => 'नमी की बहुत कमी—तुरंत सिंचाई करें';

  @override
  String get account => 'खाता';

  @override
  String helloUser(Object name) {
    return 'नमस्ते, $name';
  }

  @override
  String get noPhone => 'कोई फोन नहीं';

  @override
  String get myFields => 'मेरे खेत';

  @override
  String get governmentSchemes => 'सरकारी योजनाएँ';

  @override
  String get logout => 'लॉगआउट';

  @override
  String get refreshUserData => 'उपयोगकर्ता जानकारी ताज़ा करें';

  @override
  String get noUserIdFound => 'उपयोगकर्ता आईडी नहीं मिली। कृपया लॉगिन करें।';

  @override
  String errorFetchingUserData(Object message) {
    return 'उपयोगकर्ता जानकारी लेने में गलती: $message';
  }

  @override
  String errorLoggingOut(Object message) {
    return 'लॉगआउट करने में गलती: $message';
  }

  @override
  String errorDecodingField(Object message) {
    return 'खेत की जानकारी समझने में गलती: $message';
  }

  @override
  String selectedField(Object fieldName) {
    return 'चुना हुआ खेत: $fieldName';
  }

  @override
  String get pradhanMantriFasalBimaYojana => 'प्रधानमंत्री फसल बीमा योजना';

  @override
  String get kisanCreditCardScheme => 'किसान क्रेडिट कार्ड योजना';

  @override
  String get paramparagatKrishiVikasYojana => 'परंपरागत खेती विकास योजना';

  @override
  String get yourSelectedField => 'आपका चुना हुआ खेत';

  @override
  String get loadingFieldMap => 'खेत का नक्शा लोड हो रहा है...';

  @override
  String get farmMatrixAssistant => 'फार्ममैट्रिक्स सहायक';

  @override
  String get chatHistory => 'चैट का इतिहास';

  @override
  String get newChat => 'नई चैट';

  @override
  String get askYourAssistant => 'अपने सहायक से पूछें';

  @override
  String get askAnything => 'कुछ भी पूछें';

  @override
  String get rename => 'नाम बदलें';

  @override
  String get delete => 'हटाएँ';

  @override
  String get renameChat => 'चैट का नाम बदलें';

  @override
  String get enterNewChatName => 'नया चैट नाम डालें';

  @override
  String get deleteChat => 'चैट हटाएँ';

  @override
  String get deleteChatConfirmation => 'क्या आप सचमुच इस चैट को हटाना चाहते हैं? इसे वापस नहीं लाया जा सकता।';

  @override
  String get apiErrorMessage => 'माफ करें, आपका अनुरोध पूरा नहीं हुआ। फिर से कोशिश करें।';
}
