<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                       xsi:schemaLocation="http://www.opengis.net/sld
http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd" version="1.0.0">
    <NamedLayer>
        <Name>reds_percent</Name>
        <UserStyle>
            <Title>reds_percent</Title>
            <FeatureTypeStyle>
                <Rule>
                    <RasterSymbolizer>
                        <ColorMap>
                            <ColorMapEntry color="#f7fbff" quantity="0.0" label="0%"/>
                            <ColorMapEntry color="#d1e2f3" quantity="0.2" label="20%"/>
                            <ColorMapEntry color="#9ac8e0" quantity="0.4" label="40%"/>
                            <ColorMapEntry color="#529dcc" quantity="0.6" label="60%"/>
                            <ColorMapEntry color="#1d6cb1" quantity="0.8" label="80%"/>
                            <ColorMapEntry color="#08306b" quantity="1.0" label="100%"/>
                        </ColorMap>
                        <Opacity>1.0</Opacity>
                    </RasterSymbolizer>
                </Rule>
            </FeatureTypeStyle>
        </UserStyle>
    </NamedLayer>
</StyledLayerDescriptor>
