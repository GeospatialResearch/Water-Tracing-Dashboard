<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                       xsi:schemaLocation="http://www.opengis.net/sld
http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd" version="1.0.0">
    <NamedLayer>
        <Name>watersource_hydros_mean</Name>
        <UserStyle>
            <Title>watersource_hydros_mean</Title>
            <FeatureTypeStyle>
                <Rule>
                    <RasterSymbolizer>
                        <ColorMap>
                            <ColorMapEntry color="#440154" quantity="0" label="0%"/>
                            <ColorMapEntry color="#414487" quantity="51" label="20%"/>
                            <ColorMapEntry color="#2a788e" quantity="102" label="40%"/>
                            <ColorMapEntry color="#22a884" quantity="153" label="60%"/>
                            <ColorMapEntry color="#7ad151" quantity="204" label="80%"/>
                            <ColorMapEntry color="#fde725" quantity="255" label="100%"/>
                        </ColorMap>
                        <Opacity>1.0</Opacity>
                    </RasterSymbolizer>
                </Rule>
            </FeatureTypeStyle>
        </UserStyle>
    </NamedLayer>
</StyledLayerDescriptor>
