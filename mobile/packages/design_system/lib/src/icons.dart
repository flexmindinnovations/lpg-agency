import 'package:flutter/widgets.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';
import 'package:lucide_icons_flutter/lucide_icons_600.dart';

/// Every icon the mobile apps draw, named for what it means rather than what
/// it looks like.
///
/// Screens never import an icon font directly: they ask for
/// `LpgIcons.orders`, not `LucideIcons.receiptText`. That keeps the two
/// apps visually consistent and makes swapping the icon set (or a single
/// glyph, when brand guidelines arrive) a change to this file only.
///
/// The set is Lucide (lucide.dev): consistent 2px-stroke outline icons. The
/// default stroke is Lucide's regular weight; the `*Filled` variants use its
/// heavier 600 weight, for selected states (the active bottom-navigation
/// tab) where weight carries the selection, not just colour.
abstract final class LpgIcons {
  // Navigation
  static const IconData home = LucideIcons.house;
  static const IconData homeFilled = LucideIcons600.house;
  static const IconData orders = LucideIcons.receiptText;
  static const IconData ordersFilled = LucideIcons600.receiptText;
  static const IconData support = LucideIcons.headset;
  static const IconData supportFilled = LucideIcons600.headset;
  static const IconData profile = LucideIcons.circleUser;
  static const IconData profileFilled = LucideIcons600.circleUser;
  static const IconData notifications = LucideIcons.bell;
  static const IconData notificationsFilled = LucideIcons600.bell;
  static const IconData notificationsOff = LucideIcons.bellOff;
  static const IconData today = LucideIcons.calendarCheck;
  static const IconData todayFilled = LucideIcons600.calendarCheck;
  static const IconData deliveries = LucideIcons.truck;
  static const IconData deliveriesFilled = LucideIcons600.truck;
  static const IconData chevronRight = LucideIcons.chevronRight;
  static const IconData chevronDown = LucideIcons.chevronDown;
  static const IconData back = LucideIcons.arrowLeft;
  static const IconData external = LucideIcons.arrowUpRight;

  // Domain
  static const IconData cylinder = LucideIcons.cylinder;
  static const IconData flame = LucideIcons.flame;
  static const IconData refill = LucideIcons.fuel;
  static const IconData truck = LucideIcons.truck;
  static const IconData truckFilled = LucideIcons600.truck;
  static const IconData van = LucideIcons.truck;
  static const IconData route = LucideIcons.route;
  static const IconData package = LucideIcons.package;
  static const IconData inventory = LucideIcons.boxes;
  static const IconData invoice = LucideIcons.fileText;
  static const IconData receipt = LucideIcons.receipt;
  static const IconData payment = LucideIcons.creditCard;
  static const IconData wallet = LucideIcons.wallet;
  static const IconData cash = LucideIcons.banknote;
  static const IconData handover = LucideIcons.handCoins;
  static const IconData rupee = LucideIcons.indianRupee;
  static const IconData kyc = LucideIcons.idCard;
  static const IconData badge = LucideIcons.idCard;
  static const IconData verified = LucideIcons.badgeCheck;
  static const IconData verifiedFilled = LucideIcons600.badgeCheck;
  static const IconData unverified = LucideIcons.badgeAlert;
  static const IconData complaint = LucideIcons.messageSquareText;
  static const IconData announcement = LucideIcons.megaphone;
  static const IconData signature = LucideIcons.signature;
  static const IconData agency = LucideIcons.store;

  // Places and time
  static const IconData location = LucideIcons.mapPin;
  static const IconData locationFilled = LucideIcons600.mapPin;
  static const IconData addLocation = LucideIcons.mapPinPlus;
  static const IconData locationOff = LucideIcons.mapPinOff;
  static const IconData myLocation = LucideIcons.locateFixed;
  static const IconData locating = LucideIcons.locate;
  static const IconData navigate = LucideIcons.navigation;
  static const IconData map = LucideIcons.map;
  static const IconData recenter = LucideIcons.crosshair;
  static const IconData calendar = LucideIcons.calendar;
  static const IconData clock = LucideIcons.clock;
  static const IconData timer = LucideIcons.timer;
  static const IconData history = LucideIcons.history;
  static const IconData pending = LucideIcons.hourglass;

  // Status
  static const IconData success = LucideIcons.circleCheckBig;
  static const IconData successFilled = LucideIcons600.circleCheckBig;
  static const IconData check = LucideIcons.check;
  static const IconData allDone = LucideIcons.checkCheck;
  static const IconData error = LucideIcons.circleAlert;
  static const IconData warning = LucideIcons.triangleAlert;
  static const IconData info = LucideIcons.info;
  static const IconData cancel = LucideIcons.circleX;
  static const IconData blocked = LucideIcons.ban;
  static const IconData paused = LucideIcons.circlePause;
  static const IconData circle = LucideIcons.circle;
  static const IconData flag = LucideIcons.flag;
  static const IconData star = LucideIcons.star;
  static const IconData sparkle = LucideIcons.sparkles;

  // Connectivity and sync
  static const IconData sync = LucideIcons.refreshCw;
  static const IconData syncProblem = LucideIcons.triangleAlert;
  static const IconData offline = LucideIcons.cloudOff;
  static const IconData synced = LucideIcons.cloudCheck;
  static const IconData upload = LucideIcons.cloudUpload;

  // People and contact
  static const IconData user = LucideIcons.user;
  static const IconData userOff = LucideIcons.userMinus;
  static const IconData phone = LucideIcons.phone;
  static const IconData call = LucideIcons.phoneCall;
  static const IconData email = LucideIcons.mail;

  // Actions
  static const IconData add = LucideIcons.plus;
  static const IconData addCircle = LucideIcons.circlePlus;
  static const IconData remove = LucideIcons.minus;
  static const IconData removeCircle = LucideIcons.circleMinus;
  static const IconData edit = LucideIcons.pencil;
  static const IconData delete = LucideIcons.trash2;
  static const IconData copy = LucideIcons.copy;
  static const IconData share = LucideIcons.share2;
  static const IconData download = LucideIcons.download;
  static const IconData search = LucideIcons.search;
  static const IconData filter = LucideIcons.funnel;
  static const IconData settings = LucideIcons.settings;
  static const IconData logout = LucideIcons.logOut;
  static const IconData close = LucideIcons.x;
  static const IconData lock = LucideIcons.lock;
  static const IconData security = LucideIcons.shieldCheck;
  static const IconData number = LucideIcons.hash;
  static const IconData help = LucideIcons.circleHelp;
  static const IconData lifebuoy = LucideIcons.lifeBuoy;

  // Media
  static const IconData camera = LucideIcons.camera;
  static const IconData addPhoto = LucideIcons.imagePlus;
  static const IconData gallery = LucideIcons.images;
  static const IconData imageBroken = LucideIcons.imageOff;
  static const IconData warehouse = LucideIcons.warehouse;
  static const IconData chat = LucideIcons.messageCircle;
  static const IconData grid = LucideIcons.layoutGrid;
  static const IconData empty = LucideIcons.inbox;
}
