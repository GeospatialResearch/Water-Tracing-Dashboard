<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                       xsi:schemaLocation="http://www.opengis.net/sld
http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd" version="1.0.0">
    <NamedLayer>
        <Name>viridis_raster_0p0005max</Name>
        <UserStyle>
            <Title>Viridis Raster 0.0005 max</Title>
            <FeatureTypeStyle>
                <Rule>
                    <RasterSymbolizer>
                        <ColorMap>
                            <ColorMapEntry color="#440154" quantity="0.000" label="0.0 mm"/>
                            <ColorMapEntry color="#414487" quantity="0.0001" label="0.1 mm"/>
                            <ColorMapEntry color="#2a788e" quantity="0.0002" label="0.2 mm"/>
                            <ColorMapEntry color="#22a884" quantity="0.0003" label="0.3 mm"/>
                            <ColorMapEntry color="#7ad151" quantity="0.0004" label="0.4 mm"/>
                            <ColorMapEntry color="#fde725" quantity="0.0005" label="0.5 mm"/>
                        </ColorMap>
                        <Opacity>1.0</Opacity>
                    </RasterSymbolizer>
                </Rule>
            </FeatureTypeStyle>
        </UserStyle>
    </NamedLayer>
</StyledLayerDescriptor>
