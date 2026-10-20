import { FormControl } from '@angular/forms';
import { notBlank, selectableByName } from './form-validators';

describe('notBlank', () => {
  it.each([
    ['', { required: true }],
    ['   ', { required: true }],
    ['Kukatpally', null],
  ])('%p -> %p', (value, expected) => {
    expect(notBlank(new FormControl(value))).toEqual(expected);
  });
});

describe('selectableByName', () => {
  it('drops inactive and blank-named records', () => {
    const items = [
      { id: 1, name: 'Main', is_active: true },
      { id: 2, name: 'Old', is_active: false },
      { id: 3, name: '  ', is_active: true },
    ];
    expect(selectableByName(items).map((i) => i.id)).toEqual([1]);
  });
});
