<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                       xsi:schemaLocation="http://www.opengis.net/sld
http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd" version="1.0.0">
    <NamedLayer>
        <Name>viridis_raster_20max</Name>
        <UserStyle>
            <Title>Viridis Raster 20 max</Title>
            <FeatureTypeStyle>
                <Rule>
                    <RasterSymbolizer>
                        <ColorMap>
                            <ColorMapEntry color="#440154" quantity="0" label="0 m"/>
                            <ColorMapEntry color="#414487" quantity="4" label="3 m"/>
                            <ColorMapEntry color="#2a788e" quantity="8" label="8 m"/>
                            <ColorMapEntry color="#22a884" quantity="12" label="12 m"/>
                            <ColorMapEntry color="#7ad151" quantity="16" label="16 m"/>
                            <ColorMapEntry color="#fde725" quantity="20" label="20 m"/>
                        </ColorMap>
                        <Opacity>1.0</Opacity>
                    </RasterSymbolizer>
                </Rule>
            </FeatureTypeStyle>
        </UserStyle>
    </NamedLayer>
</StyledLayerDescriptor>
