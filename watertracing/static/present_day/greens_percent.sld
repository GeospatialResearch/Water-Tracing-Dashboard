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
                            <ColorMapEntry color="#f7fcf5" quantity="0.0" label="0%"/>
                            <ColorMapEntry color="#d5efcf" quantity="0.2" label="20%"/>
                            <ColorMapEntry color="#9ed798" quantity="0.4" label="40%"/>
                            <ColorMapEntry color="#55b567" quantity="0.6" label="60%"/>
                            <ColorMapEntry color="#1d8641" quantity="0.8" label="80%"/>
                            <ColorMapEntry color="#00441b" quantity="1.0" label="100%"/>
                        </ColorMap>
                        <Opacity>1.0</Opacity>
                    </RasterSymbolizer>
                </Rule>
            </FeatureTypeStyle>
        </UserStyle>
    </NamedLayer>
</StyledLayerDescriptor>
