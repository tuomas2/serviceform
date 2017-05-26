from colorful.fields import RGBColorField


class ColorField(RGBColorField):
    def get_prep_value(self, value: 'ColorStr') -> 'Optional[ColorStr]':
        rv = super().get_prep_value(value)
        if rv == '#000000':
            rv = None
        return rv

    def from_db_value(self, value: 'Optional[ColorStr]', *args):
        if value is None:
            return '#000000'
        return value