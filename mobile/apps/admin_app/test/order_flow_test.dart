import 'package:admin_app/src/features/orders/domain/order_flow.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('OrderActions', () {
    test('a booked order can be confirmed or cancelled, nothing else', () {
      const actions = OrderActions('booked');
      expect(actions.canConfirm, isTrue);
      expect(actions.canCancelNow, isTrue);
      expect(actions.canSendOut, isFalse);
      expect(actions.canRecordDelivery, isFalse);
    });

    test('confirmed and assigned orders can be sent out', () {
      expect(const OrderActions('confirmed').canSendOut, isTrue);
      expect(const OrderActions('assigned').canSendOut, isTrue);
      expect(const OrderActions('ready_for_dispatch').canSendOut, isFalse);
    });

    test('a loaded order waits for the driver to leave', () {
      const actions = OrderActions('ready_for_dispatch');
      expect(actions.canDepart, isTrue);
      expect(actions.canCancelNow, isTrue);
    });

    test('an order out for delivery records delivery or asks to cancel', () {
      const actions = OrderActions('out_for_delivery');
      expect(actions.canRecordDelivery, isTrue);
      expect(actions.canCancelNow, isFalse);
      expect(actions.canRequestCancellation, isTrue);
      expect(actions.canReviewCancellation, isFalse);
    });

    test('a waiting cancellation request is reviewed, not asked again', () {
      const actions = OrderActions(
        'out_for_delivery',
        hasPendingCancellation: true,
      );
      expect(actions.canReviewCancellation, isTrue);
      expect(actions.canRequestCancellation, isFalse);
    });

    test('a failed delivery is rescheduled; a delivered order is closed', () {
      expect(const OrderActions('failed_delivery').canReschedule, isTrue);
      expect(const OrderActions('delivered').canClose, isTrue);
      expect(const OrderActions('cancelled').canCancelNow, isFalse);
      expect(const OrderActions('closed').canClose, isFalse);
    });
  });

  group('progress', () {
    test('maps each status to a step; cancelled has none', () {
      expect(orderProgressIndex('booked'), 0);
      expect(orderProgressIndex('assigned'), 2);
      expect(orderProgressIndex('ready_for_dispatch'), 2);
      expect(orderProgressIndex('failed_delivery'), 3);
      expect(orderProgressIndex('closed'), 4);
      expect(orderProgressIndex('cancelled'), isNull);
    });

    test('the note names the trip when it is known', () {
      expect(
        orderProgressNote('assigned', tripLabel: 'MH12 AB 1234 with Ravi'),
        'On MH12 AB 1234 with Ravi. The van still needs loading.',
      );
      expect(
        orderProgressNote('ready_for_dispatch'),
        'Loaded, waiting for the driver to leave.',
      );
      expect(orderProgressNote('cancelled'), isNull);
    });
  });

  group('chips', () {
    test('every filter label is sentence case', () {
      for (final filter in orderFilters) {
        expect(filter.label, isNot(equals(filter.label.toUpperCase())));
        expect(filter.label[0], filter.label[0].toUpperCase());
      }
    });

    test('filters cover the real statuses', () {
      final onTrip = orderFilters.firstWhere((f) => f.label == 'On a trip');
      expect(onTrip.matches('assigned'), isTrue);
      expect(onTrip.matches('ready_for_dispatch'), isTrue);
      expect(onTrip.matches('booked'), isFalse);
      expect(orderFilters.first.matches('anything'), isTrue);
    });

    test('status chips read in sentence case', () {
      expect(LpgFormat.statusLabel('out_for_delivery'), 'Out for delivery');
      expect(LpgFormat.statusLabel('failed_delivery'), 'Failed delivery');
    });

    test('status colours', () {
      expect(orderStatusSeverity('delivered'), LpgStatusSeverity.success);
      expect(orderStatusSeverity('failed_delivery'), LpgStatusSeverity.danger);
      expect(orderStatusSeverity('out_for_delivery'), LpgStatusSeverity.info);
    });
  });

  test('send-out errors are put in the counter staff\'s words', () {
    expect(sendOutErrorMessage('INSUFFICIENT_STOCK'), contains('godown'));
    expect(sendOutErrorMessage('SOMETHING_ELSE'), isNull);
  });
}
