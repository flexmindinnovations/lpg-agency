// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'app_database.dart';

// ignore_for_file: type=lint
class $SchemaMetadataTable extends SchemaMetadata
    with TableInfo<$SchemaMetadataTable, SchemaMetadataData> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $SchemaMetadataTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _keyMeta = const VerificationMeta('key');
  @override
  late final GeneratedColumn<String> key = GeneratedColumn<String>(
    'key',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _valueMeta = const VerificationMeta('value');
  @override
  late final GeneratedColumn<String> value = GeneratedColumn<String>(
    'value',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [key, value];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'schema_metadata';
  @override
  VerificationContext validateIntegrity(
    Insertable<SchemaMetadataData> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('key')) {
      context.handle(
        _keyMeta,
        key.isAcceptableOrUnknown(data['key']!, _keyMeta),
      );
    } else if (isInserting) {
      context.missing(_keyMeta);
    }
    if (data.containsKey('value')) {
      context.handle(
        _valueMeta,
        value.isAcceptableOrUnknown(data['value']!, _valueMeta),
      );
    } else if (isInserting) {
      context.missing(_valueMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {key};
  @override
  SchemaMetadataData map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return SchemaMetadataData(
      key: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}key'],
      )!,
      value: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}value'],
      )!,
    );
  }

  @override
  $SchemaMetadataTable createAlias(String alias) {
    return $SchemaMetadataTable(attachedDatabase, alias);
  }
}

class SchemaMetadataData extends DataClass
    implements Insertable<SchemaMetadataData> {
  final String key;
  final String value;
  const SchemaMetadataData({required this.key, required this.value});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['key'] = Variable<String>(key);
    map['value'] = Variable<String>(value);
    return map;
  }

  SchemaMetadataCompanion toCompanion(bool nullToAbsent) {
    return SchemaMetadataCompanion(key: Value(key), value: Value(value));
  }

  factory SchemaMetadataData.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return SchemaMetadataData(
      key: serializer.fromJson<String>(json['key']),
      value: serializer.fromJson<String>(json['value']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'key': serializer.toJson<String>(key),
      'value': serializer.toJson<String>(value),
    };
  }

  SchemaMetadataData copyWith({String? key, String? value}) =>
      SchemaMetadataData(key: key ?? this.key, value: value ?? this.value);
  SchemaMetadataData copyWithCompanion(SchemaMetadataCompanion data) {
    return SchemaMetadataData(
      key: data.key.present ? data.key.value : this.key,
      value: data.value.present ? data.value.value : this.value,
    );
  }

  @override
  String toString() {
    return (StringBuffer('SchemaMetadataData(')
          ..write('key: $key, ')
          ..write('value: $value')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(key, value);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is SchemaMetadataData &&
          other.key == this.key &&
          other.value == this.value);
}

class SchemaMetadataCompanion extends UpdateCompanion<SchemaMetadataData> {
  final Value<String> key;
  final Value<String> value;
  final Value<int> rowid;
  const SchemaMetadataCompanion({
    this.key = const Value.absent(),
    this.value = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  SchemaMetadataCompanion.insert({
    required String key,
    required String value,
    this.rowid = const Value.absent(),
  }) : key = Value(key),
       value = Value(value);
  static Insertable<SchemaMetadataData> custom({
    Expression<String>? key,
    Expression<String>? value,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (key != null) 'key': key,
      if (value != null) 'value': value,
      if (rowid != null) 'rowid': rowid,
    });
  }

  SchemaMetadataCompanion copyWith({
    Value<String>? key,
    Value<String>? value,
    Value<int>? rowid,
  }) {
    return SchemaMetadataCompanion(
      key: key ?? this.key,
      value: value ?? this.value,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (key.present) {
      map['key'] = Variable<String>(key.value);
    }
    if (value.present) {
      map['value'] = Variable<String>(value.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('SchemaMetadataCompanion(')
          ..write('key: $key, ')
          ..write('value: $value, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $SyncOperationsTable extends SyncOperations
    with TableInfo<$SyncOperationsTable, SyncOperation> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $SyncOperationsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<String> id = GeneratedColumn<String>(
    'id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _typeMeta = const VerificationMeta('type');
  @override
  late final GeneratedColumn<String> type = GeneratedColumn<String>(
    'type',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _payloadMeta = const VerificationMeta(
    'payload',
  );
  @override
  late final GeneratedColumn<String> payload = GeneratedColumn<String>(
    'payload',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _statusMeta = const VerificationMeta('status');
  @override
  late final GeneratedColumn<String> status = GeneratedColumn<String>(
    'status',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
    defaultValue: const Constant('pending'),
  );
  static const VerificationMeta _createdAtMeta = const VerificationMeta(
    'createdAt',
  );
  @override
  late final GeneratedColumn<DateTime> createdAt = GeneratedColumn<DateTime>(
    'created_at',
    aliasedName,
    false,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: false,
    defaultValue: currentDateAndTime,
  );
  static const VerificationMeta _errorMessageMeta = const VerificationMeta(
    'errorMessage',
  );
  @override
  late final GeneratedColumn<String> errorMessage = GeneratedColumn<String>(
    'error_message',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _idempotencyKeyMeta = const VerificationMeta(
    'idempotencyKey',
  );
  @override
  late final GeneratedColumn<String> idempotencyKey = GeneratedColumn<String>(
    'idempotency_key',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
    defaultConstraints: GeneratedColumn.constraintIsAlways('UNIQUE'),
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    type,
    payload,
    status,
    createdAt,
    errorMessage,
    idempotencyKey,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'sync_operations';
  @override
  VerificationContext validateIntegrity(
    Insertable<SyncOperation> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    } else if (isInserting) {
      context.missing(_idMeta);
    }
    if (data.containsKey('type')) {
      context.handle(
        _typeMeta,
        type.isAcceptableOrUnknown(data['type']!, _typeMeta),
      );
    } else if (isInserting) {
      context.missing(_typeMeta);
    }
    if (data.containsKey('payload')) {
      context.handle(
        _payloadMeta,
        payload.isAcceptableOrUnknown(data['payload']!, _payloadMeta),
      );
    } else if (isInserting) {
      context.missing(_payloadMeta);
    }
    if (data.containsKey('status')) {
      context.handle(
        _statusMeta,
        status.isAcceptableOrUnknown(data['status']!, _statusMeta),
      );
    }
    if (data.containsKey('created_at')) {
      context.handle(
        _createdAtMeta,
        createdAt.isAcceptableOrUnknown(data['created_at']!, _createdAtMeta),
      );
    }
    if (data.containsKey('error_message')) {
      context.handle(
        _errorMessageMeta,
        errorMessage.isAcceptableOrUnknown(
          data['error_message']!,
          _errorMessageMeta,
        ),
      );
    }
    if (data.containsKey('idempotency_key')) {
      context.handle(
        _idempotencyKeyMeta,
        idempotencyKey.isAcceptableOrUnknown(
          data['idempotency_key']!,
          _idempotencyKeyMeta,
        ),
      );
    } else if (isInserting) {
      context.missing(_idempotencyKeyMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id};
  @override
  SyncOperation map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return SyncOperation(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}id'],
      )!,
      type: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}type'],
      )!,
      payload: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}payload'],
      )!,
      status: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}status'],
      )!,
      createdAt: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}created_at'],
      )!,
      errorMessage: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}error_message'],
      ),
      idempotencyKey: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}idempotency_key'],
      )!,
    );
  }

  @override
  $SyncOperationsTable createAlias(String alias) {
    return $SyncOperationsTable(attachedDatabase, alias);
  }
}

class SyncOperation extends DataClass implements Insertable<SyncOperation> {
  final String id;
  final String type;
  final String payload;
  final String status;
  final DateTime createdAt;
  final String? errorMessage;
  final String idempotencyKey;
  const SyncOperation({
    required this.id,
    required this.type,
    required this.payload,
    required this.status,
    required this.createdAt,
    this.errorMessage,
    required this.idempotencyKey,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<String>(id);
    map['type'] = Variable<String>(type);
    map['payload'] = Variable<String>(payload);
    map['status'] = Variable<String>(status);
    map['created_at'] = Variable<DateTime>(createdAt);
    if (!nullToAbsent || errorMessage != null) {
      map['error_message'] = Variable<String>(errorMessage);
    }
    map['idempotency_key'] = Variable<String>(idempotencyKey);
    return map;
  }

  SyncOperationsCompanion toCompanion(bool nullToAbsent) {
    return SyncOperationsCompanion(
      id: Value(id),
      type: Value(type),
      payload: Value(payload),
      status: Value(status),
      createdAt: Value(createdAt),
      errorMessage: errorMessage == null && nullToAbsent
          ? const Value.absent()
          : Value(errorMessage),
      idempotencyKey: Value(idempotencyKey),
    );
  }

  factory SyncOperation.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return SyncOperation(
      id: serializer.fromJson<String>(json['id']),
      type: serializer.fromJson<String>(json['type']),
      payload: serializer.fromJson<String>(json['payload']),
      status: serializer.fromJson<String>(json['status']),
      createdAt: serializer.fromJson<DateTime>(json['createdAt']),
      errorMessage: serializer.fromJson<String?>(json['errorMessage']),
      idempotencyKey: serializer.fromJson<String>(json['idempotencyKey']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<String>(id),
      'type': serializer.toJson<String>(type),
      'payload': serializer.toJson<String>(payload),
      'status': serializer.toJson<String>(status),
      'createdAt': serializer.toJson<DateTime>(createdAt),
      'errorMessage': serializer.toJson<String?>(errorMessage),
      'idempotencyKey': serializer.toJson<String>(idempotencyKey),
    };
  }

  SyncOperation copyWith({
    String? id,
    String? type,
    String? payload,
    String? status,
    DateTime? createdAt,
    Value<String?> errorMessage = const Value.absent(),
    String? idempotencyKey,
  }) => SyncOperation(
    id: id ?? this.id,
    type: type ?? this.type,
    payload: payload ?? this.payload,
    status: status ?? this.status,
    createdAt: createdAt ?? this.createdAt,
    errorMessage: errorMessage.present ? errorMessage.value : this.errorMessage,
    idempotencyKey: idempotencyKey ?? this.idempotencyKey,
  );
  SyncOperation copyWithCompanion(SyncOperationsCompanion data) {
    return SyncOperation(
      id: data.id.present ? data.id.value : this.id,
      type: data.type.present ? data.type.value : this.type,
      payload: data.payload.present ? data.payload.value : this.payload,
      status: data.status.present ? data.status.value : this.status,
      createdAt: data.createdAt.present ? data.createdAt.value : this.createdAt,
      errorMessage: data.errorMessage.present
          ? data.errorMessage.value
          : this.errorMessage,
      idempotencyKey: data.idempotencyKey.present
          ? data.idempotencyKey.value
          : this.idempotencyKey,
    );
  }

  @override
  String toString() {
    return (StringBuffer('SyncOperation(')
          ..write('id: $id, ')
          ..write('type: $type, ')
          ..write('payload: $payload, ')
          ..write('status: $status, ')
          ..write('createdAt: $createdAt, ')
          ..write('errorMessage: $errorMessage, ')
          ..write('idempotencyKey: $idempotencyKey')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    id,
    type,
    payload,
    status,
    createdAt,
    errorMessage,
    idempotencyKey,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is SyncOperation &&
          other.id == this.id &&
          other.type == this.type &&
          other.payload == this.payload &&
          other.status == this.status &&
          other.createdAt == this.createdAt &&
          other.errorMessage == this.errorMessage &&
          other.idempotencyKey == this.idempotencyKey);
}

class SyncOperationsCompanion extends UpdateCompanion<SyncOperation> {
  final Value<String> id;
  final Value<String> type;
  final Value<String> payload;
  final Value<String> status;
  final Value<DateTime> createdAt;
  final Value<String?> errorMessage;
  final Value<String> idempotencyKey;
  final Value<int> rowid;
  const SyncOperationsCompanion({
    this.id = const Value.absent(),
    this.type = const Value.absent(),
    this.payload = const Value.absent(),
    this.status = const Value.absent(),
    this.createdAt = const Value.absent(),
    this.errorMessage = const Value.absent(),
    this.idempotencyKey = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  SyncOperationsCompanion.insert({
    required String id,
    required String type,
    required String payload,
    this.status = const Value.absent(),
    this.createdAt = const Value.absent(),
    this.errorMessage = const Value.absent(),
    required String idempotencyKey,
    this.rowid = const Value.absent(),
  }) : id = Value(id),
       type = Value(type),
       payload = Value(payload),
       idempotencyKey = Value(idempotencyKey);
  static Insertable<SyncOperation> custom({
    Expression<String>? id,
    Expression<String>? type,
    Expression<String>? payload,
    Expression<String>? status,
    Expression<DateTime>? createdAt,
    Expression<String>? errorMessage,
    Expression<String>? idempotencyKey,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (type != null) 'type': type,
      if (payload != null) 'payload': payload,
      if (status != null) 'status': status,
      if (createdAt != null) 'created_at': createdAt,
      if (errorMessage != null) 'error_message': errorMessage,
      if (idempotencyKey != null) 'idempotency_key': idempotencyKey,
      if (rowid != null) 'rowid': rowid,
    });
  }

  SyncOperationsCompanion copyWith({
    Value<String>? id,
    Value<String>? type,
    Value<String>? payload,
    Value<String>? status,
    Value<DateTime>? createdAt,
    Value<String?>? errorMessage,
    Value<String>? idempotencyKey,
    Value<int>? rowid,
  }) {
    return SyncOperationsCompanion(
      id: id ?? this.id,
      type: type ?? this.type,
      payload: payload ?? this.payload,
      status: status ?? this.status,
      createdAt: createdAt ?? this.createdAt,
      errorMessage: errorMessage ?? this.errorMessage,
      idempotencyKey: idempotencyKey ?? this.idempotencyKey,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<String>(id.value);
    }
    if (type.present) {
      map['type'] = Variable<String>(type.value);
    }
    if (payload.present) {
      map['payload'] = Variable<String>(payload.value);
    }
    if (status.present) {
      map['status'] = Variable<String>(status.value);
    }
    if (createdAt.present) {
      map['created_at'] = Variable<DateTime>(createdAt.value);
    }
    if (errorMessage.present) {
      map['error_message'] = Variable<String>(errorMessage.value);
    }
    if (idempotencyKey.present) {
      map['idempotency_key'] = Variable<String>(idempotencyKey.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('SyncOperationsCompanion(')
          ..write('id: $id, ')
          ..write('type: $type, ')
          ..write('payload: $payload, ')
          ..write('status: $status, ')
          ..write('createdAt: $createdAt, ')
          ..write('errorMessage: $errorMessage, ')
          ..write('idempotencyKey: $idempotencyKey, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

abstract class _$AppDatabase extends GeneratedDatabase {
  _$AppDatabase(QueryExecutor e) : super(e);
  $AppDatabaseManager get managers => $AppDatabaseManager(this);
  late final $SchemaMetadataTable schemaMetadata = $SchemaMetadataTable(this);
  late final $SyncOperationsTable syncOperations = $SyncOperationsTable(this);
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [
    schemaMetadata,
    syncOperations,
  ];
}

typedef $$SchemaMetadataTableCreateCompanionBuilder =
    SchemaMetadataCompanion Function({
      required String key,
      required String value,
      Value<int> rowid,
    });
typedef $$SchemaMetadataTableUpdateCompanionBuilder =
    SchemaMetadataCompanion Function({
      Value<String> key,
      Value<String> value,
      Value<int> rowid,
    });

class $$SchemaMetadataTableFilterComposer
    extends Composer<_$AppDatabase, $SchemaMetadataTable> {
  $$SchemaMetadataTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get key => $composableBuilder(
    column: $table.key,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get value => $composableBuilder(
    column: $table.value,
    builder: (column) => ColumnFilters(column),
  );
}

class $$SchemaMetadataTableOrderingComposer
    extends Composer<_$AppDatabase, $SchemaMetadataTable> {
  $$SchemaMetadataTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get key => $composableBuilder(
    column: $table.key,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get value => $composableBuilder(
    column: $table.value,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$SchemaMetadataTableAnnotationComposer
    extends Composer<_$AppDatabase, $SchemaMetadataTable> {
  $$SchemaMetadataTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get key =>
      $composableBuilder(column: $table.key, builder: (column) => column);

  GeneratedColumn<String> get value =>
      $composableBuilder(column: $table.value, builder: (column) => column);
}

class $$SchemaMetadataTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $SchemaMetadataTable,
          SchemaMetadataData,
          $$SchemaMetadataTableFilterComposer,
          $$SchemaMetadataTableOrderingComposer,
          $$SchemaMetadataTableAnnotationComposer,
          $$SchemaMetadataTableCreateCompanionBuilder,
          $$SchemaMetadataTableUpdateCompanionBuilder,
          (
            SchemaMetadataData,
            BaseReferences<
              _$AppDatabase,
              $SchemaMetadataTable,
              SchemaMetadataData
            >,
          ),
          SchemaMetadataData,
          PrefetchHooks Function()
        > {
  $$SchemaMetadataTableTableManager(
    _$AppDatabase db,
    $SchemaMetadataTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$SchemaMetadataTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$SchemaMetadataTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$SchemaMetadataTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> key = const Value.absent(),
                Value<String> value = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) =>
                  SchemaMetadataCompanion(key: key, value: value, rowid: rowid),
          createCompanionCallback:
              ({
                required String key,
                required String value,
                Value<int> rowid = const Value.absent(),
              }) => SchemaMetadataCompanion.insert(
                key: key,
                value: value,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$SchemaMetadataTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $SchemaMetadataTable,
      SchemaMetadataData,
      $$SchemaMetadataTableFilterComposer,
      $$SchemaMetadataTableOrderingComposer,
      $$SchemaMetadataTableAnnotationComposer,
      $$SchemaMetadataTableCreateCompanionBuilder,
      $$SchemaMetadataTableUpdateCompanionBuilder,
      (
        SchemaMetadataData,
        BaseReferences<_$AppDatabase, $SchemaMetadataTable, SchemaMetadataData>,
      ),
      SchemaMetadataData,
      PrefetchHooks Function()
    >;
typedef $$SyncOperationsTableCreateCompanionBuilder =
    SyncOperationsCompanion Function({
      required String id,
      required String type,
      required String payload,
      Value<String> status,
      Value<DateTime> createdAt,
      Value<String?> errorMessage,
      required String idempotencyKey,
      Value<int> rowid,
    });
typedef $$SyncOperationsTableUpdateCompanionBuilder =
    SyncOperationsCompanion Function({
      Value<String> id,
      Value<String> type,
      Value<String> payload,
      Value<String> status,
      Value<DateTime> createdAt,
      Value<String?> errorMessage,
      Value<String> idempotencyKey,
      Value<int> rowid,
    });

class $$SyncOperationsTableFilterComposer
    extends Composer<_$AppDatabase, $SyncOperationsTable> {
  $$SyncOperationsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get type => $composableBuilder(
    column: $table.type,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get payload => $composableBuilder(
    column: $table.payload,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get status => $composableBuilder(
    column: $table.status,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get errorMessage => $composableBuilder(
    column: $table.errorMessage,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get idempotencyKey => $composableBuilder(
    column: $table.idempotencyKey,
    builder: (column) => ColumnFilters(column),
  );
}

class $$SyncOperationsTableOrderingComposer
    extends Composer<_$AppDatabase, $SyncOperationsTable> {
  $$SyncOperationsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get type => $composableBuilder(
    column: $table.type,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get payload => $composableBuilder(
    column: $table.payload,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get status => $composableBuilder(
    column: $table.status,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get errorMessage => $composableBuilder(
    column: $table.errorMessage,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get idempotencyKey => $composableBuilder(
    column: $table.idempotencyKey,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$SyncOperationsTableAnnotationComposer
    extends Composer<_$AppDatabase, $SyncOperationsTable> {
  $$SyncOperationsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get type =>
      $composableBuilder(column: $table.type, builder: (column) => column);

  GeneratedColumn<String> get payload =>
      $composableBuilder(column: $table.payload, builder: (column) => column);

  GeneratedColumn<String> get status =>
      $composableBuilder(column: $table.status, builder: (column) => column);

  GeneratedColumn<DateTime> get createdAt =>
      $composableBuilder(column: $table.createdAt, builder: (column) => column);

  GeneratedColumn<String> get errorMessage => $composableBuilder(
    column: $table.errorMessage,
    builder: (column) => column,
  );

  GeneratedColumn<String> get idempotencyKey => $composableBuilder(
    column: $table.idempotencyKey,
    builder: (column) => column,
  );
}

class $$SyncOperationsTableTableManager
    extends
        RootTableManager<
          _$AppDatabase,
          $SyncOperationsTable,
          SyncOperation,
          $$SyncOperationsTableFilterComposer,
          $$SyncOperationsTableOrderingComposer,
          $$SyncOperationsTableAnnotationComposer,
          $$SyncOperationsTableCreateCompanionBuilder,
          $$SyncOperationsTableUpdateCompanionBuilder,
          (
            SyncOperation,
            BaseReferences<_$AppDatabase, $SyncOperationsTable, SyncOperation>,
          ),
          SyncOperation,
          PrefetchHooks Function()
        > {
  $$SyncOperationsTableTableManager(
    _$AppDatabase db,
    $SyncOperationsTable table,
  ) : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$SyncOperationsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$SyncOperationsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$SyncOperationsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> id = const Value.absent(),
                Value<String> type = const Value.absent(),
                Value<String> payload = const Value.absent(),
                Value<String> status = const Value.absent(),
                Value<DateTime> createdAt = const Value.absent(),
                Value<String?> errorMessage = const Value.absent(),
                Value<String> idempotencyKey = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => SyncOperationsCompanion(
                id: id,
                type: type,
                payload: payload,
                status: status,
                createdAt: createdAt,
                errorMessage: errorMessage,
                idempotencyKey: idempotencyKey,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String id,
                required String type,
                required String payload,
                Value<String> status = const Value.absent(),
                Value<DateTime> createdAt = const Value.absent(),
                Value<String?> errorMessage = const Value.absent(),
                required String idempotencyKey,
                Value<int> rowid = const Value.absent(),
              }) => SyncOperationsCompanion.insert(
                id: id,
                type: type,
                payload: payload,
                status: status,
                createdAt: createdAt,
                errorMessage: errorMessage,
                idempotencyKey: idempotencyKey,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$SyncOperationsTableProcessedTableManager =
    ProcessedTableManager<
      _$AppDatabase,
      $SyncOperationsTable,
      SyncOperation,
      $$SyncOperationsTableFilterComposer,
      $$SyncOperationsTableOrderingComposer,
      $$SyncOperationsTableAnnotationComposer,
      $$SyncOperationsTableCreateCompanionBuilder,
      $$SyncOperationsTableUpdateCompanionBuilder,
      (
        SyncOperation,
        BaseReferences<_$AppDatabase, $SyncOperationsTable, SyncOperation>,
      ),
      SyncOperation,
      PrefetchHooks Function()
    >;

class $AppDatabaseManager {
  final _$AppDatabase _db;
  $AppDatabaseManager(this._db);
  $$SchemaMetadataTableTableManager get schemaMetadata =>
      $$SchemaMetadataTableTableManager(_db, _db.schemaMetadata);
  $$SyncOperationsTableTableManager get syncOperations =>
      $$SyncOperationsTableTableManager(_db, _db.syncOperations);
}
